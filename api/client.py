import requests
import os
import concurrent.futures
import traceback
from urllib.parse import urlparse
from datetime import datetime
import asyncio
import pyppeteer
from io import BytesIO

from .report_generator import generate_html_report

def _find_chrome_executable():
    """A helper to find Google Chrome on Windows in common locations."""
    for path in [
        os.path.join(os.environ.get("ProgramFiles", "C:/Program Files"), "Google/Chrome/Application/chrome.exe"),
        os.path.join(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)"), "Google/Chrome/Application/chrome.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google/Chrome/Application/chrome.exe"),
    ]:
        if os.path.exists(path):
            return path
    return None

class PestCareClient:
    """
    Handles all API interactions and file downloading.
    Uses a hybrid approach: fetches data via API, generates a local HTML file,
    and then uses a headless browser to print that HTML to a perfect PDF.
    """
    def __init__(self, db_handler):
        self.base_url = "https://api.pestcare.id"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.auth_token = None
        self.account_info = None
        self.db_handler = db_handler
        self.browser = None
        self.chrome_path = "" # Will be set from the GUI

    def set_chrome_path(self, path):
        """Allows the GUI to set the chrome path from config."""
        self.chrome_path = path

    async def _get_browser(self, log_callback):
        """Initializes and returns a headless browser instance, creating it if it doesn't exist."""
        if self.browser is None or not self.browser.connected:
            log_callback("Initializing headless browser for PDF generation...")
            
            executable_path = self.chrome_path
            if not executable_path or not os.path.exists(executable_path):
                log_callback(" - User-defined Chrome path not found or not set. Trying to auto-detect...")
                executable_path = _find_chrome_executable()

            if not executable_path:
                log_callback(" - Could not auto-detect Chrome. Falling back to pyppeteer's default (may download Chromium).")
                try:
                    executable_path = pyppeteer.launcher.executablePath()
                except Exception as e:
                     log_callback(f"FATAL: Failed to download or find Chromium. Error: {e}")
                     return None
            
            log_callback(f" - Using browser from: {executable_path}")

            try:
                self.browser = await pyppeteer.launch(
                    executablePath=executable_path,
                    headless=True,
                    args=['--no-sandbox', '--disable-setuid-sandbox'],
                    handleSIGINT=False, handleSIGTERM=False, handleSIGHUP=False
                )
                log_callback(" - Browser initialized successfully.")
            except Exception as e:
                log_callback(f"FATAL: Could not launch browser. PDFs cannot be generated. Error: {e}")
                log_callback("TIP: Please ensure Google Chrome is installed and the path is set correctly in 'Browser Settings...'")
                self.browser = None
        return self.browser
    
    async def close_browser(self):
        if self.browser and self.browser.connected:
            await self.browser.close()
            self.browser = None

    def is_logged_in(self): return self.auth_token is not None

    def login_and_get_technicians(self, username, password):
        login_url = f"{self.base_url}/web/api/auth/login"
        payload = {"username": username, "password": password}
        try:
            response = self.session.post(login_url, json=payload, timeout=20)
            response.raise_for_status()
            data = response.json()
            if data.get("code") == 200 and "accessToken" in data.get("body", {}):
                self.auth_token = data["body"]["accessToken"]
                self.account_info = data["body"].get("account")
                self.session.headers.update({"Authorization": f"Bearer {self.auth_token}"})
                branch_id = self.account_info.get("employee_branch_id")
                techs = self._fetch_api_data(f"/web/api/employee/no-paging", {'branch_id': branch_id})
                return True, techs
            return False, None
        except requests.exceptions.RequestException: return False, None

    def _fetch_api_data(self, endpoint, params=None, method='GET', json_payload=None):
        url = f"{self.base_url}{endpoint}"
        try:
            if method.upper() == 'GET': response = self.session.get(url, params=params, timeout=20)
            elif method.upper() == 'POST': response = self.session.post(url, json=json_payload, timeout=20)
            else: return None
            response.raise_for_status()
            data = response.json()
            return data.get("body") or data.get("data")
        except (requests.exceptions.RequestException, ValueError): return None
    
    def _sanitize_report_data(self, report):
        """Ensures all expected list keys exist and are lists, preventing errors."""
        list_keys = ["report_detail_feedbacks", "report_detail_treatments", "report_detail_chemicals", "report_detail_type_works", "uploaded_files"]
        for key in list_keys:
            if not isinstance(report.get(key), list):
                report[key] = []
        return report

    def _sync_clients(self, log_callback):
        branch_id = self.account_info.get("employee_branch_id")
        clients = self._fetch_api_data("/web/api/client/no-paging", {'branch_id': branch_id})
        if clients:
            self.db_handler.sync_clients(clients)
            log_callback(f"Successfully synced {len(clients)} clients.")
            return {c['id']: c for c in clients}
        log_callback("Warning: Could not fetch or sync client list.")
        return {}

    async def fetch_and_download_all_data(self, log_callback, max_workers, output_folder, start_date, end_date, selected_tech_ids, download_pdfs, download_images):
        if not self.is_logged_in():
            log_callback("Cannot start sync. Please log in first."); return
        
        loop = asyncio.get_running_loop()
        clients_dict = await loop.run_in_executor(None, self._sync_clients, log_callback)
        if not clients_dict:
            log_callback("Aborting sync: Failed to get client list."); return

        if download_pdfs:
            browser = await self._get_browser(log_callback)
            if not browser:
                log_callback("Could not start browser. PDF downloads will be skipped.")
                download_pdfs = False

        total_images, total_pdfs = 0, 0
        for i, (client_id, client_data) in enumerate(clients_dict.items()):
            client_name = client_data.get('name', f"Client_{client_id}")
            log_callback(f"\n[{i+1}/{len(clients_dict)}] Processing Client: {client_name}")
            contracts = self._fetch_api_data(f"/web/api/contract/{client_id}/client", {'is_void': 'yes'})
            if not contracts:
                log_callback("  - No contracts found."); continue
            
            for contract in contracts:
                contract_id = contract.get('id')
                if not contract_id: continue

                # *** FIX: Fetch detailed contract info to get the address ***
                check_report_payload = {"contract_id": contract_id}
                full_contract_data = self._fetch_api_data("/web/api/report/check-report-service", json_payload=check_report_payload, method='POST')
                
                sts_payload = {"contract_id": contract_id, "employee_ids": selected_tech_ids}
                sts_reports = self._fetch_api_data("/web/api/report/form-sts", json_payload=sts_payload, method='POST')
                if not sts_reports: continue

                reports_in_range = self._filter_reports_by_date(sts_reports, start_date, end_date)
                if not reports_in_range: continue
                
                log_callback(f"  - Found {len(reports_in_range)} STS report(s) in date range for Contract ID {contract_id}.")

                if download_images:
                    img_count = self._process_images_for_reports(reports_in_range, client_name, output_folder, max_workers, log_callback)
                    total_images += img_count
                
                if download_pdfs:
                    # Pass the newly fetched detailed contract data
                    pdf_count = await self._process_pdfs_for_reports(reports_in_range, full_contract_data, client_name, output_folder, log_callback)
                    total_pdfs += pdf_count
        
        log_callback("\n-------------------------------------------")
        log_callback("Smart Sync process finished.")
        if download_images: log_callback(f"Downloaded {total_images} new image(s).")
        if download_pdfs: log_callback(f"Generated {total_pdfs} new PDF report(s).")

    def _filter_reports_by_date(self, reports, start_date_str, end_date_str):
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        filtered = []
        for report in reports:
            try:
                report_date = datetime.strptime(report.get('date_work'), '%Y-%m-%d').date()
                if start_date <= report_date <= end_date:
                    filtered.append(report)
            except (ValueError, TypeError): continue
        return filtered

    def _process_images_for_reports(self, reports, client_name, output_folder, max_workers, log_callback):
        files_to_download = []
        for report in reports:
            schedule_id = report.get('schedule_id')
            technician_name = report.get('employee_name', 'Unknown_Technician')
            if not schedule_id: continue
            payload = {"schedule_id": schedule_id, "type": "sts"}
            uploaded_files = self._fetch_api_data("/web/api/schedule/file-uploaded", json_payload=payload, method='POST')
            if not uploaded_files: continue
            for file_data in uploaded_files:
                file_url, file_id = file_data.get('filename'), file_data.get('id')
                if not file_url or not file_id: continue
                ext = os.path.splitext(urlparse(file_url).path)[1] or '.jpg'
                filename = f"ReportImage_{schedule_id}_{file_id}{ext}"
                category = os.path.join("".join(c for c in technician_name if c.isalnum() or c in (' ', '_')).rstrip(), "".join(c for c in client_name if c.isalnum() or c in (' ', '_')).rstrip(), "Foto")
                if not self.db_handler.is_already_downloaded(filename, category):
                    files_to_download.append({'url': file_url, 'filename': filename, 'technician_name': technician_name, 'client_name': client_name})
        if not files_to_download: return 0
        log_callback(f"    - Found {len(files_to_download)} new images. Starting parallel download...")
        count = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_file = {executor.submit(self._download_image_worker, f_info, output_folder): f_info for f_info in files_to_download}
            for future in concurrent.futures.as_completed(future_to_file):
                try:
                    success, fname = future.result()
                    if success:
                        count += 1; log_callback(f"      -> SUCCESS (Image): {fname}")
                    else: log_callback(f"      -> FAILED (Image): {fname}")
                except Exception as exc: log_callback(f"      -> ERROR downloading {future_to_file[future]['filename']}: {exc}")
        return count

    def _download_image_worker(self, file_info, download_folder):
        sane_tech = "".join(c for c in file_info['technician_name'] if c.isalnum() or c in (' ', '_')).rstrip()
        sane_client = "".join(c for c in file_info['client_name'] if c.isalnum() or c in (' ', '_')).rstrip()
        category = os.path.join(sane_tech, sane_client, "Foto")
        download_path = os.path.join(download_folder, category)
        os.makedirs(download_path, exist_ok=True)
        file_path = os.path.join(download_path, file_info['filename'])
        try:
            with self.session.get(file_info['url'], stream=True, timeout=60) as r:
                r.raise_for_status()
                with open(file_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192): f.write(chunk)
            self.db_handler.add_download_record(file_info['filename'], category, file_info['url'])
            return (True, file_info['filename'])
        except requests.exceptions.RequestException: return (False, file_info['filename'])

    async def _process_pdfs_for_reports(self, reports, full_contract_data, client_name, output_folder, log_callback):
        count = 0
        contract_info = full_contract_data.get("contract", {}) if full_contract_data else {}
        client_info_details = contract_info.get("clients", {})
        branch_name = contract_info.get("branches", {}).get("name", "N/A")
        client_address = client_info_details.get("address", "N/A")

        for report in reports:
            report = self._sanitize_report_data(report) # Sanitize each report
            schedule_id = report.get('schedule_id')
            technician_name = report.get('employee_name', 'Unknown_Technician')
            if not schedule_id: continue
            
            payload = {"schedule_id": schedule_id, "type": "sts"}
            report['uploaded_files'] = self._fetch_api_data("/web/api/schedule/file-uploaded", json_payload=payload, method='POST') or []
            
            report_date = report.get('date_work', 'nodate')
            filename = f"STS_Report_{client_name.replace('/', '_')}_{report_date}_{schedule_id}.pdf"
            category = os.path.join("".join(c for c in technician_name if c.isalnum() or c in (' ', '_')).rstrip(), "".join(c for c in client_name if c.isalnum() or c in (' ', '_')).rstrip(), "STS Reports")
            
            if self.db_handler.is_already_downloaded(filename, category): continue
            
            log_callback(f"    - Generating PDF for schedule {schedule_id}...")
            
            pdf_path = os.path.join(output_folder, category)
            os.makedirs(pdf_path, exist_ok=True)
            full_file_path = os.path.join(pdf_path, filename)
            
            try:
                client_full_info = {"address": client_address, "branch_name": branch_name}
                source_html = generate_html_report(report, client_full_info, self.session)
                
                page = await self.browser.newPage()
                await page.setContent(source_html)
                await page.pdf({'path': full_file_path, 'format': 'A4'})
                await page.close()
                
                self.db_handler.add_download_record(filename, category, f"api_generated_{schedule_id}")
                log_callback(f"      -> SUCCESS (PDF): {filename}")
                count += 1
            except Exception as e:
                log_callback(f"      -> FAILED (PDF): Exception during PDF generation for schedule {schedule_id}. Reason: {e}")
        return count

