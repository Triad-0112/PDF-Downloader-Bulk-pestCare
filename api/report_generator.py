import base64
from io import BytesIO
import requests
from datetime import datetime
import os

# Cache for downloaded images to avoid fetching them multiple times.
IMAGE_CACHE = {}
# A 1x1 transparent GIF to use as a placeholder for failed/missing images.
PLACEHOLDER_TRANSPARENT_PIXEL = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"

# --- SVG Checkbox Images (Base64 Encoded) ---
# This is the most reliable way to render custom checkboxes in PDFs.
CHECKED_BOX_SVG = "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxNiIgaGVpZ2h0PSIxNiIgdmlld0JveD0iMCAwIDE2IDE2Ij48cmVjdCB3aWR0aD0iMTYiIGhlaWdodD0iMTYiIHJ4PSI0IiBmaWxsPSIjMjU2M2ViIi8+PHBhdGggZD0iTTEyLjIwNyA0Ljc5M2ExIDEgMCAwMTAgMS40MTRsLTUgNWExIDEgMCAwMS0xLjQxNCAwbC0yLTJhMSAxIDAgMDExLjQxNC0xLjQxNEw2LjUgOS4wODZsNC4yOTMtNC4yOTNhMSAxIDAgMDExLjQxNCAweiIgZmlsbD0id2hpdGUiLz48L3N2Zz4="
UNCHECKED_BOX_SVG = "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxNiIgaGVpZ2h0PSIxNiIgdmlld0JveD0iMCAwIDE2IDE2Ij48cmVjdCB4PSIwLjUiIHk9IjAuNSIgd2lkdGg9IjE1IiBoZWlnaHQ9IjE1IiByeD0iMy41IiBmaWxsPSJ3aGl0ZSIgc3Ryb2tlPSIjNmI3MjgwIi8+PC9zdmc+"


# Mapping of product names to their LOCAL logo file paths
PRODUCT_LOGOS = {
    "ProServe+": "images/Logo ProServePlus-1ebed8c6.png",
    "MaxxGuard": "images/Logo MaxxGuard-1f60aee0.png",
    "PrimeShield": "images/Logo Primeshield-af83d41e.png"
}

def get_image_as_base64(path_or_url, session):
    """
    Downloads an image from a URL or reads a local file and converts it 
    to a base64 data URI for embedding.
    """
    if not path_or_url:
        return PLACEHOLDER_TRANSPARENT_PIXEL

    if path_or_url in IMAGE_CACHE:
        return IMAGE_CACHE[path_or_url]

    # Handle web URLs
    if path_or_url.startswith('http'):
        try:
            response = session.get(path_or_url, timeout=15)
            response.raise_for_status()
            content = response.content
            content_type = response.headers.get('Content-Type', 'image/png').lower()
            img_format = 'jpeg' if 'jpeg' in content_type or 'jpg' in content_type else 'png'
        except requests.exceptions.RequestException:
            return PLACEHOLDER_TRANSPARENT_PIXEL
    # Handle local file paths
    else:
        try:
            if not os.path.exists(path_or_url):
                print(f"Warning: Local image not found at {path_or_url}")
                return PLACEHOLDER_TRANSPARENT_PIXEL
            with open(path_or_url, 'rb') as f:
                content = f.read()
            img_format = 'png' if path_or_url.lower().endswith('.png') else 'jpeg'
        except IOError:
            return PLACEHOLDER_TRANSPARENT_PIXEL
            
    encoded_string = base64.b64encode(content).decode('utf-8')
    data_uri = f"data:image/{img_format};base64,{encoded_string}"
    IMAGE_CACHE[path_or_url] = data_uri
    return data_uri

def generate_html_report(report_data, client_info, session):
    """
    Generates a self-contained HTML document for a report, using the original website's CSS
    for perfect rendering by a headless browser.
    """
    # --- Original Website CSS ---
    original_css = """
    @charset "UTF-8";
    @import"https://fonts.googleapis.com/css2?family=Poppins:ital,wght@0,100;0,200;0,300;0,400;0,500;0,600;0,700;0,800;0,900;1,100;1,200;1,300;1,400;1,500;1,600;1,700;1,800;1,900&display=swap";
    *,:before,:after{box-sizing:border-box;border-width:0;border-style:solid;border-color:#e5e7eb}
    body{font-family:Poppins,sans-serif}
    """
    
    # --- Helper functions for building HTML sections ---
    def format_datetime(date_str, format_out):
        if not date_str: return "N/A"
        try:
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return dt.strftime(format_out)
        except (ValueError, TypeError):
            try: return datetime.strptime(date_str, '%Y-%m-%d').strftime(format_out)
            except (ValueError, TypeError): return date_str

    def get_report_number(report):
        seq = report.get('sequence_number')
        total = report.get('visit_total_base_period_contract')
        if isinstance(seq, int) and isinstance(total, int): return f"{seq} / {total}"
        return "N/A"

    def build_checkbox_grid(items, class_name):
        if not items: return "<p>N/A</p>"
        html = f'<div class="{class_name}">'
        for item in items:
            label_text = item.get("name") or item.get("type_work_name") or "N/A"
            checkbox_svg = CHECKED_BOX_SVG if item.get('selected') == 1 else UNCHECKED_BOX_SVG
            html += f"""
            <div class="checkbox-item">
                <img src="{checkbox_svg}" class="custom-checkbox" />
                <label>{label_text}</label>
            </div>
            """
        html += '</div>'
        return html
        
    def build_chemicals_table(items):
        if not items: return "<tr><td colspan='5' style='text-align:center;'>No chemical data available.</td></tr>"
        rows_html = ""
        for item in items:
            rows_html += f"""
            <tr>
                <td>{item.get("active_ingredient", "")}</td>
                <td>{item.get("dosis", "")}</td>
                <td>{item.get("no_batch", "")}</td>
                <td>{item.get("method_application_name", "")}</td>
                <td>{item.get("total_usage", "")} {item.get("uom_name", "")}</td>
            </tr>
            """
        return rows_html

    def build_uploaded_images(items, session):
        if not items: return "<p>No files uploaded.</p>"
        html = '<div class="image-grid">'
        for item in items:
            img_b64 = get_image_as_base64(item.get("filename"), session)
            note = item.get("notes", "")
            html += f"""
            <div class="image-cell">
                <img src="{img_b64}" />
                <p>{note}</p>
            </div>
            """
        html += '</div>'
        return html

    product_name = report_data.get('product_service_name', 'ProServe+')
    product_logo_path = PRODUCT_LOGOS.get(product_name, PRODUCT_LOGOS['ProServe+'])

    # --- Main HTML Template ---
    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>STS Report</title>
        <style>
            {original_css}
            @page {{ size: a4 portrait; margin: 0.8cm; }}
            body {{ font-family: 'Poppins', sans-serif; font-size: 8.5pt; color: #333; }}
            .report-container {{ width: 100%; }}
            table {{ border-collapse: collapse; width: 100%; }}
            td {{ vertical-align: top; padding: 0; }}

            /* Header */
            .header-logo {{ width: 160px; }}
            .header-address {{ text-align: left; font-size: 8.5pt; line-height: 1.4; padding-left: 20px; }}
            .header-address .address-detail {{ font-size: 7.5pt; font-weight: normal; }}
            .header-hr {{ border: 0; border-top: 1px solid #000; margin: 8px 0; }}
            .title {{ font-size: 14pt; font-weight: bold; text-align: center; padding-bottom: 4px; border-bottom: 2px solid #000; margin-bottom: 10px; }}

            /* Info Grid */
            .info-grid {{ table-layout: fixed; }}
            .info-grid td {{ padding-bottom: 8px; }}
            .info-label {{ font-weight: bold; font-size: 8.5pt; }}
            .info-value {{ font-size: 8.5pt; }}
            .product-logo {{ max-height: 40px; }}

            /* Sections */
            .section-title {{ font-weight: bold; text-decoration: underline; margin-top: 10px; margin-bottom: 5px; font-size: 10pt; }}
            .italic-note {{ font-style: italic; font-size: 8pt; margin: 10px 0; }}
            
            /* Checkboxes */
            .checkbox-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 4px 15px; }}
            .checkbox-item {{ display: flex; align-items: center; }}
            .custom-checkbox {{ height: 1rem; width: 1rem; margin-right: 5px; }}
            .checkbox-item label {{ vertical-align: middle; }}

            /* Chemicals Table */
            .chemicals-table {{ margin-top: 5px; }}
            .chemicals-table th, .chemicals-table td {{ border: 1px solid #000; padding: 4px; text-align: center; font-size: 8pt; }}

            /* Notes */
            .notes {{ margin-top: 8px; }}
            .notes-label {{ font-weight: bold; }}

            /* Images */
            .page-break-container {{ page-break-inside: avoid; }}
            .image-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }}
            .image-cell {{ text-align: center; }}
            .image-cell img {{ max-width: 100%; height: 150px; object-fit: contain; border: 1px solid #ccc; margin-bottom: 3px; }}
            .image-cell p {{ font-size: 8pt; margin-top: 0; }}

            /* Footer */
            .footer-text {{ font-size: 8pt; margin-top: 15px; }}
            .signatures {{ margin-top: 20px; table-layout: fixed; }}
            .signatures td {{ width: 50%; vertical-align: bottom; text-align: center; font-size: 9pt; }}
            .signatures img {{ width: 120px; height: 60px; object-fit: contain; margin: 10px auto; }}
            .signatures hr {{ width: 150px; margin: 0 auto; border-top: 1px solid #333; }}
        </style>
    </head>
    <body>
        <div class="report-container">
            <table>
                <tr>
                    <td style="width: 50%; vertical-align: middle;">
                        <img class="header-logo" src="{get_image_as_base64('images/Logo_Secondary_ecoCare_Pest_Control-63c7d801.png', session)}">
                    </td>
                    <td class="header-address" style="vertical-align: middle;">
                        <div>Head office:</div>
                        <div><b>PT Indocitra Pacific</b></div>
                        <div class="address-detail">Grand Slipi Tower Suite F-I 37th floor Jl. S. Parman Kav. 22-24 Jakarta 11480 (021) 290 222 66 | info@ecocare.co.id</div>
                    </td>
                </tr>
            </table>
            <hr class="header-hr"/>
            <div class="title">SERVICE TREATMENT SLIP (BERITA ACARA SERVICE)</div>

            <table class="info-grid">
                 <tr>
                    <td style="width: 33%;"><div class="info-label">Branch :</div><div class="info-value">{client_info.get("branch_name", "N/A")}</div></td>
                    <td style="width: 33%;"><div class="info-label">Time IN :</div><div class="info-value">{format_datetime(report_data.get('checkin_time'), '%b %dth %y, %I:%M %p')}</div></td>
                    <td style="width: 34%; position: relative;">
                        <div class="info-label">Time OUT :</div>
                        <div class="info-value">{format_datetime(report_data.get('checkout_time'), '%b %dth %y, %I:%M %p')}</div>
                        <img class="product-logo" src="{get_image_as_base64(product_logo_path, session)}" style="position: absolute; right: 0; top: 0;">
                    </td>
                </tr>
                <tr>
                    <td><div class="info-label">Report No :</div><div class="info-value">{get_report_number(report_data)}</div></td>
                    <td><div class="info-label">Date :</div><div class="info-value">{format_datetime(report_data.get('date_work'), '%b %dth %y')}</div></td>
                    <td><div class="info-label">Paket Program :</div><div class="info-value">{report_data.get('product_service_name', 'N/A')}</div></td>
                </tr>
                <tr>
                    <td colspan="3" style="padding-top: 5px;">
                        <div class="info-label">Client Information :</div>
                        <div class="info-value">{report_data.get("client_name", "N/A")}</div>
                        <div class="info-value">{client_info.get("address", "N/A")}</div>
                    </td>
                </tr>
            </table>

            <div class="italic-note"><b>This is to advise you that our technician will carry out our service duties at your premises as follows :</b></div>
            
            <div class="section-title">Type of Service</div>
            {build_checkbox_grid(report_data.get("report_detail_treatments"), "checkbox-grid")}
            <div class="notes">
                <span class="notes-label">Others (Please Specify):</span>
                <span>{report_data.get("note_type_service", "") or "&nbsp;"}</span>
            </div>

            <div class="section-title">Type of Work</div>
            {build_checkbox_grid(report_data.get("report_detail_type_works"), "checkbox-grid")}
            <div class="notes">
                <span class="notes-label">Others:</span>
                <span>{report_data.get("note_type_work", "") or "&nbsp;"}</span>
            </div>

            <div class="section-title">Pesticide Detail</div>
            <table class="chemicals-table">
                <thead><tr><th>Active Ingredient</th><th>Dosis/Kons</th><th>Batch Number</th><th>Method of Application</th><th>Total Usage</th></tr></thead>
                <tbody>{build_chemicals_table(report_data.get("report_detail_chemicals"))}</tbody>
            </table>

            <div class="notes">
                <div class="notes-label">Action Taken:</div>
                <div>{report_data.get("note_action_taken", "N/A") or "&nbsp;"}</div>
            </div>
            <div class="notes">
                <div class="notes-label">Remarks:</div>
                <div>{report_data.get("note_remark", "N/A") or "&nbsp;"}</div>
            </div>

            <div class="page-break-container">
                <div class="section-title">File Uploaded:</div>
                {build_uploaded_images(report_data.get("uploaded_files"), session)}

                <div class="footer-text">With this, it is our pleasure to inform you that all service requested has been completed well and delivered accordingly. I/We agree that all work has been performed to a satisfactory standard.</div>
                
                <table class="signatures">
                    <tr>
                        <td>
                            <b>Signature Client</b><br/>
                            <img src="{get_image_as_base64(report_data.get('url_signature_client'), session)}" /><br/>
                            <hr/>
                            <span>{report_data.get("signature_client_name", "")}</span>
                        </td>
                        <td>
                            <b>Technician</b><br/>
                            <img src="{get_image_as_base64(report_data.get('url_signature_employee'), session)}" /><br/>
                            <hr/>
                            <span>{report_data.get("employee_name", "")}</span>
                        </td>
                    </tr>
                </table>
            </div>
        </div>
    </body>
    </html>
    """
    return html_template

