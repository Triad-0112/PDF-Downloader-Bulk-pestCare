import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import threading
import configparser
import os
from datetime import datetime, timedelta
import sys
import traceback
import asyncio

from api.client import PestCareClient
from database.handler import DatabaseHandler

class SettingsDialog(tk.Toplevel):
    """A dialog for configuring application settings like the Chrome path."""
    def __init__(self, parent):
        super().__init__(parent)
        self.transient(parent)
        self.title("Settings")
        self.parent = parent
        self.result = None
        self.grab_set()
        
        body = ttk.Frame(self, padding="10 10 10 10")
        self.initial_focus = self.create_widgets(body)
        body.pack(padx=5, pady=5)

        self.protocol("WM_DELETE_WINDOW", self.cancel)
        if not self.initial_focus:
            self.initial_focus = self

        self.initial_focus.focus_set()
        self.wait_window(self)

    def create_widgets(self, master):
        master.columnconfigure(1, weight=1)
        
        ttk.Label(master, text="Chrome Executable Path:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        
        self.chrome_path_var = tk.StringVar()
        self.chrome_path_entry = ttk.Entry(master, textvariable=self.chrome_path_var, width=60)
        self.chrome_path_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=5)

        browse_button = ttk.Button(master, text="Browse...", command=self.browse_for_chrome)
        browse_button.grid(row=0, column=2, padx=5, pady=5)

        button_frame = ttk.Frame(master)
        button_frame.grid(row=1, column=0, columnspan=3, pady=10)

        save_button = ttk.Button(button_frame, text="Save", command=self.save_and_close)
        save_button.pack(side=tk.LEFT, padx=5)
        cancel_button = ttk.Button(button_frame, text="Cancel", command=self.cancel)
        cancel_button.pack(side=tk.LEFT, padx=5)
        
        return self.chrome_path_entry

    def browse_for_chrome(self):
        # On Windows, look for chrome.exe
        filetypes = [('Executable files', '*.exe'), ('All files', '.*')]
        filepath = filedialog.askopenfilename(
            title="Select Google Chrome Executable",
            filetypes=filetypes,
            initialdir=os.environ.get("ProgramFiles(x86)", "C:/")
        )
        if filepath:
            self.chrome_path_var.set(filepath)

    def save_and_close(self):
        self.parent.config.set('Settings', 'chrome_executable_path', self.chrome_path_var.get())
        with open(self.parent.config_path, 'w') as configfile:
            self.parent.config.write(configfile)
        self.parent.log_message("Chrome path saved in config.ini.")
        self.parent.load_config() # Reload config in main window
        self.destroy()

    def cancel(self):
        self.destroy()

class App(tk.Tk):
    """The main GUI application window."""
    def __init__(self):
        super().__init__()
        self.title("PestCare Bulk Downloader")
        self.geometry("800x750")
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.config = configparser.ConfigParser()
        self.config_path = 'config.ini'
        self.chrome_path = "" # To store the path

        # --- Style Configuration ---
        self.style = ttk.Style(self)
        self.style.theme_use('clam')
        self.BG_COLOR = "#f0f0f0"
        self.PRIMARY_COLOR = "#0078d4"
        self.PRIMARY_ACTIVE_COLOR = "#005a9e"
        self.SECONDARY_COLOR = "#d9534f"
        self.SECONDARY_ACTIVE_COLOR = "#c9302c"
        self.TEXT_COLOR = "#333333"
        self.ENTRY_BG = "#ffffff"
        self.configure(bg=self.BG_COLOR)
        self.style.configure("TFrame", background=self.BG_COLOR)
        self.style.configure("TLabel", background=self.BG_COLOR, foreground=self.TEXT_COLOR, font=("Segoe UI", 10))
        self.style.configure("TLabelframe", background=self.BG_COLOR, bordercolor="#cccccc", relief="solid")
        self.style.configure("TLabelframe.Label", background=self.BG_COLOR, foreground=self.TEXT_COLOR, font=("Segoe UI", 11, "bold"))
        self.style.configure("TButton", padding=8, relief="flat", font=("Segoe UI", 10, "bold"), background=self.PRIMARY_COLOR, foreground="white")
        self.style.map("TButton", background=[('active', self.PRIMARY_ACTIVE_COLOR), ('disabled', '#cccccc')])
        self.style.configure("Danger.TButton", background=self.SECONDARY_COLOR)
        self.style.map("Danger.TButton", background=[('active', self.SECONDARY_ACTIVE_COLOR)])
        self.style.configure("TEntry", fieldbackground=self.ENTRY_BG, bordercolor="#cccccc", foreground=self.TEXT_COLOR, insertcolor=self.TEXT_COLOR, padding=5)
        self.style.configure("TCheckbutton", background=self.BG_COLOR, font=("Segoe UI", 9))
        
        # --- Database and API Client ---
        self.db_handler = DatabaseHandler()
        self.api_client = PestCareClient(self.db_handler)
        self.technicians = {} 
        self.technician_vars = {} 

        self.create_widgets()
        self.load_config()
        self.setup_exception_handler()

    def setup_exception_handler(self):
        def handle_exception(exc_type, exc_value, exc_traceback):
            error_message = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
            self.log_message(f"\n--- UNCAUGHT EXCEPTION ---\n{error_message}\n--------------------------")
            messagebox.showerror("Unhandled Application Error", f"A critical error occurred:\n\n{exc_value}\n\nThe application will now close.")
            self.on_closing(force=True)
        sys.excepthook = handle_exception
        self.report_callback_exception = handle_exception
        threading.excepthook = lambda args: self.after(0, handle_exception, args.exc_type, args.exc_value, args.exc_traceback)

    def create_widgets(self):
        main_frame = ttk.Frame(self, padding="20 20 20 20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(3, weight=1)

        top_frame = ttk.Frame(main_frame)
        top_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        top_frame.columnconfigure(0, weight=1)
        top_frame.columnconfigure(1, weight=1)

        creds_frame = ttk.LabelFrame(top_frame, text="1. Login", padding=(15, 10))
        creds_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        creds_frame.columnconfigure(1, weight=1)
        
        ttk.Label(creds_frame, text="Username:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.username_entry = ttk.Entry(creds_frame)
        self.username_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        ttk.Label(creds_frame, text="Password:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.password_entry = ttk.Entry(creds_frame, show="*")
        self.password_entry.grid(row=1, column=1, sticky="ew", padx=5, pady=5)
        self.login_button = ttk.Button(creds_frame, text="Login & Fetch Technicians", command=self.perform_login)
        self.login_button.grid(row=2, column=0, columnspan=2, sticky='ew', padx=5, pady=10)

        settings_frame = ttk.LabelFrame(top_frame, text="2. General Settings", padding=(15, 10))
        settings_frame.grid(row=0, column=1, sticky="nsew")
        settings_frame.columnconfigure(1, weight=1)
        
        ttk.Label(settings_frame, text="Output Folder:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.download_path_var = tk.StringVar(value="Not set")
        path_label = ttk.Label(settings_frame, textvariable=self.download_path_var, anchor='w', relief="sunken", padding=(5, 2))
        path_label.grid(row=0, column=1, sticky='ew', padx=5, pady=5)
        ttk.Button(settings_frame, text="Change...", command=self.select_output_folder, width=10).grid(row=0, column=2, padx=5)

        ttk.Label(settings_frame, text="Workers:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.workers_var = tk.StringVar(value="4")
        self.workers_spinbox = ttk.Spinbox(settings_frame, from_=1, to=20, textvariable=self.workers_var, width=5)
        self.workers_spinbox.grid(row=1, column=1, sticky='w', padx=5, pady=5)

        settings_btn = ttk.Button(settings_frame, text="Browser Settings...", command=self.open_settings_dialog)
        settings_btn.grid(row=4, column=0, columnspan=3, sticky='ew', padx=5, pady=5)

        self.download_pdfs_var = tk.BooleanVar(value=True)
        self.download_images_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(settings_frame, text="Download PDF Reports", variable=self.download_pdfs_var).grid(row=2, column=0, columnspan=2, sticky='w', padx=5, pady=(5,0))
        ttk.Checkbutton(settings_frame, text="Download Images (Foto)", variable=self.download_images_var).grid(row=3, column=0, columnspan=2, sticky='w', padx=5, pady=(0,5))
        
        filter_frame = ttk.LabelFrame(main_frame, text="3. Smart Sync Filters", padding=(15,10))
        filter_frame.grid(row=1, column=0, sticky='ew', pady=10)
        filter_frame.columnconfigure(0, weight=1)
        filter_frame.columnconfigure(1, weight=3)

        date_frame = ttk.Frame(filter_frame)
        date_frame.grid(row=0, column=0, columnspan=2, sticky='ew', pady=5)
        ttk.Label(date_frame, text="Date Range:").pack(side=tk.LEFT, padx=5)
        self.start_date_var = tk.StringVar()
        ttk.Entry(date_frame, textvariable=self.start_date_var, width=12).pack(side=tk.LEFT, padx=5)
        ttk.Label(date_frame, text="to").pack(side=tk.LEFT, padx=5)
        self.end_date_var = tk.StringVar()
        ttk.Entry(date_frame, textvariable=self.end_date_var, width=12).pack(side=tk.LEFT, padx=5)
        ttk.Label(date_frame, text="(YYYY-MM-DD)").pack(side=tk.LEFT, padx=10)

        tech_frame = ttk.Frame(filter_frame)
        tech_frame.grid(row=1, column=0, columnspan=2, sticky='ew', pady=5)
        ttk.Label(tech_frame, text="Technicians:").grid(row=0, column=0, sticky='nw', padx=5)
        
        self.tech_canvas = tk.Canvas(tech_frame, borderwidth=0, background=self.BG_COLOR, height=100)
        self.tech_list_frame = ttk.Frame(self.tech_canvas)
        scrollbar = ttk.Scrollbar(tech_frame, orient="vertical", command=self.tech_canvas.yview)
        self.tech_canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=0, column=2, sticky='ns')
        self.tech_canvas.grid(row=0, column=1, sticky='ew')
        self.tech_canvas.create_window((4, 4), window=self.tech_list_frame, anchor="nw")
        self.tech_list_frame.bind("<Configure>", lambda e: self.tech_canvas.configure(scrollregion=self.tech_canvas.bbox("all")))
        tech_frame.columnconfigure(1, weight=1)

        select_buttons_frame = ttk.Frame(tech_frame)
        select_buttons_frame.grid(row=1, column=1, sticky='w', pady=(5,0))
        ttk.Button(select_buttons_frame, text="Select All", command=self.select_all_techs, width=12).pack(side=tk.LEFT, padx=5)
        ttk.Button(select_buttons_frame, text="Deselect All", command=self.deselect_all_techs, width=12).pack(side=tk.LEFT, padx=5)

        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.grid(row=3, column=0, sticky='nsew')
        bottom_frame.columnconfigure(0, weight=1)
        bottom_frame.rowconfigure(1, weight=1)

        control_frame = ttk.Frame(bottom_frame)
        control_frame.grid(row=0, column=0, sticky="ew", pady=10)
        
        self.download_button = ttk.Button(control_frame, text="Start Download", command=self.start_download_thread, state=tk.DISABLED)
        self.download_button.pack(side=tk.LEFT, padx=(0, 10), fill='x', expand=True)
        
        self.clear_history_button = ttk.Button(control_frame, text="Clear History", style="Danger.TButton", command=self.clear_download_history)
        self.clear_history_button.pack(side=tk.RIGHT)

        log_frame = ttk.LabelFrame(bottom_frame, text="4. Progress Log", padding=(15, 10))
        log_frame.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)

        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, state=tk.DISABLED, font=("Consolas", 9), relief="solid", borderwidth=1)
        self.log_text.grid(row=0, column=0, sticky="nsew")

        self.status_var = tk.StringVar(value="Ready. Please log in.")
        status_bar = ttk.Label(self, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W, padding=5)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def open_settings_dialog(self):
        dialog = SettingsDialog(self)
        dialog.chrome_path_var.set(self.chrome_path)

    def load_config(self):
        if not os.path.exists(self.config_path):
            self.config['Credentials'] = {'username': '', 'password': ''}
            self.config['Settings'] = {
                'default_download_folder': 'downloads',
                'max_workers': '4',
                'last_start_date': (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'),
                'last_end_date': datetime.now().strftime('%Y-%m-%d'),
                'chrome_executable_path': ''
            }
            with open(self.config_path, 'w') as configfile:
                self.config.write(configfile)
            self.log_message(f"Created default config file at '{self.config_path}'")
        
        self.config.read(self.config_path)
        username = self.config.get('Credentials', 'username', fallback='')
        password = self.config.get('Credentials', 'password', fallback='')
        self.username_entry.insert(0, username)
        self.password_entry.insert(0, password)
        if username: self.log_message(f"Credentials for '{username}' loaded.")

        folder = self.config.get('Settings', 'default_download_folder', fallback='downloads')
        self.download_path_var.set(os.path.abspath(folder))
        workers = self.config.getint('Settings', 'max_workers', fallback=4)
        self.workers_var.set(str(workers))
        start_date = self.config.get('Settings', 'last_start_date')
        end_date = self.config.get('Settings', 'last_end_date')
        self.start_date_var.set(start_date)
        self.end_date_var.set(end_date)
        
        self.chrome_path = self.config.get('Settings', 'chrome_executable_path', fallback='')
        self.api_client.set_chrome_path(self.chrome_path)
        if self.chrome_path and os.path.exists(self.chrome_path):
             self.log_message(f"Using Chrome browser from: {self.chrome_path}")
        else:
            if self.download_pdfs_var.get():
                self.log_message("WARNING: Chrome path not set or invalid. PDF downloads may fail.")
                self.log_message("Please set the path in 'Browser Settings...'")

    def save_config(self):
        if not self.config.has_section('Settings'):
            self.config.add_section('Settings')
        self.config.set('Settings', 'default_download_folder', self.download_path_var.get())
        self.config.set('Settings', 'max_workers', self.workers_var.get())
        self.config.set('Settings', 'last_start_date', self.start_date_var.get())
        self.config.set('Settings', 'last_end_date', self.end_date_var.get())
        with open(self.config_path, 'w') as configfile:
            self.config.write(configfile)
        self.log_message("Settings saved.")

    def log_message(self, message):
        def append():
            try:
                if self.log_text.winfo_exists():
                    self.log_text.configure(state=tk.NORMAL)
                    self.log_text.insert(tk.END, str(message) + "\n")
                    self.log_text.configure(state=tk.DISABLED)
                    self.log_text.see(tk.END)
            except tk.TclError:
                pass
        if self.winfo_exists():
            self.after(0, append)

    def perform_login(self):
        username = self.username_entry.get()
        password = self.password_entry.get()
        if not username or not password:
            messagebox.showerror("Error", "Username and password cannot be empty.")
            return

        self.log_message(f"Attempting to log in as {username}...")
        self.status_var.set("Logging in...")
        self.login_button.config(state=tk.DISABLED)
        threading.Thread(target=self.login_and_fetch_thread_func, args=(username, password), daemon=True).start()

    def login_and_fetch_thread_func(self, username, password):
        login_success, techs_data = self.api_client.login_and_get_technicians(username, password)
        if login_success and techs_data is not None:
            self.technicians = {tech['fullname']: tech['id'] for tech in techs_data if tech.get('fullname') and tech.get('id')}
        else:
            login_success = False # Ensure it's false if techs_data is None
        self.after(0, self.on_login_complete, login_success)

    def on_login_complete(self, success):
        self.login_button.config(state=tk.NORMAL)
        if success:
            self.log_message("Login successful!")
            self.status_var.set("Login successful. Ready to download.")
            self.download_button.config(state=tk.NORMAL)
            self.username_entry.config(state=tk.DISABLED)
            self.password_entry.config(state=tk.DISABLED)
            self.populate_technician_list()
        else:
            self.log_message("Login failed. Please check credentials and network.")
            self.status_var.set("Login failed. Please try again.")
            messagebox.showerror("Login Failed", "Could not log in.")
            
    def start_download_thread(self):
        self.status_var.set("Download in progress...")
        self.download_button.config(state=tk.DISABLED)
        self.clear_history_button.config(state=tk.DISABLED)
        try:
            max_workers = int(self.workers_var.get())
            start_date = self.start_date_var.get()
            end_date = self.end_date_var.get()
            datetime.strptime(start_date, '%Y-%m-%d')
            datetime.strptime(end_date, '%Y-%m-%d')
            download_pdfs = self.download_pdfs_var.get()
            download_images = self.download_images_var.get()
        except ValueError as e:
            messagebox.showerror("Invalid Settings", f"Please check your settings.\nError: {e}")
            self.download_button.config(state=tk.NORMAL); self.clear_history_button.config(state=tk.NORMAL)
            return
        selected_tech_ids = [self.technicians[name] for name, var in self.technician_vars.items() if var.get()]
        if not selected_tech_ids:
            messagebox.showwarning("No Technicians", "Please select at least one technician to start the download.")
            self.download_button.config(state=tk.NORMAL); self.clear_history_button.config(state=tk.NORMAL)
            return
        self.save_config()
        self.log_message(f"Starting Smart Sync for {len(selected_tech_ids)} technicians from {start_date} to {end_date}...")
        download_folder = self.download_path_var.get()
        filters = {"start_date": start_date, "end_date": end_date, "tech_ids": selected_tech_ids}
        threading.Thread(target=self.download_thread_func, args=(download_folder, max_workers, filters, download_pdfs, download_images), daemon=True).start()
    
    def download_thread_func(self, download_folder, max_workers, filters, download_pdfs, download_images):
        try:
            asyncio.run(self.api_client.fetch_and_download_all_data(
                log_callback=self.log_message,
                max_workers=max_workers,
                output_folder=download_folder,
                start_date=filters['start_date'],
                end_date=filters['end_date'],
                selected_tech_ids=filters['tech_ids'],
                download_pdfs=download_pdfs,
                download_images=download_images
            ))
            self.after(0, self.on_download_complete)
        except Exception as e:
            error_traceback = traceback.format_exc()
            self.after(0, self.on_download_error, e, error_traceback)

    def on_download_error(self, error, traceback_str):
        self.log_message(f"\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\nA CRITICAL ERROR occurred during the download process.\nError: {error}\n------------------- Traceback -------------------\n{traceback_str}\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        messagebox.showerror("Download Failed", f"An unexpected error stopped the download.\n\n{error}\n\nPlease check the log for technical details.")
        self.status_var.set("Download failed with an error.")
        self.download_button.config(state=tk.NORMAL); self.clear_history_button.config(state=tk.NORMAL)
    
    def on_download_complete(self):
        self.status_var.set("Download finished.")
        messagebox.showinfo("Complete", "The download process has finished.")
        self.download_button.config(state=tk.NORMAL); self.clear_history_button.config(state=tk.NORMAL)
    
    def clear_download_history(self):
        if messagebox.askyesno("Confirm Clear", "Are you sure you want to delete all download history? This cannot be undone."):
            self.db_handler.clear_history(); self.log_message("\nDownload history has been cleared.\n")
    
    def on_closing(self, force=False):
        if force or messagebox.askokcancel("Quit", "Do you want to exit?"):
            if self.api_client.browser:
                self.log_message("Closing headless browser...")
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_closed():
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    loop.run_until_complete(self.api_client.close_browser())
                except Exception as e:
                    print(f"Error closing browser: {e}")
            self.db_handler.close()
            self.destroy()

    def select_output_folder(self):
        folder_selected = filedialog.askdirectory(initialdir=self.download_path_var.get())
        if folder_selected:
            self.download_path_var.set(os.path.abspath(folder_selected))
            self.log_message(f"New output folder selected: {self.download_path_var.get()}")
            self.save_config()
            
    def populate_technician_list(self):
        for widget in self.tech_list_frame.winfo_children():
            widget.destroy()
        self.technician_vars = {name: tk.BooleanVar(value=True) for name in self.technicians.keys()}
        row, col = 0, 0
        for name, var in sorted(self.technician_vars.items()):
            cb = ttk.Checkbutton(self.tech_list_frame, text=name, variable=var)
            cb.grid(row=row, column=col, sticky='w', padx=5, pady=2)
            col += 1
            if col >= 3:
                col = 0
                row += 1
        self.log_message(f"Populated filter list with {len(self.technicians)} technicians.")
    def select_all_techs(self):
        for var in self.technician_vars.values(): var.set(True)
    def deselect_all_techs(self):
        for var in self.technician_vars.values(): var.set(False)

