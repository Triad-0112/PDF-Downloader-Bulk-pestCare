# PestCare Bulk Report & Image Downloader

This is a desktop application designed to efficiently download Service Treatment Slip (STS) PDF reports and associated photo evidence from the PestCare management system. It provides a graphical user interface (GUI) to simplify the process of fetching and organizing large amounts of data.

The application uses a **"Smart Sync"** feature, allowing users to filter reports by date range and by specific technicians, which dramatically speeds up the download process by only targeting relevant data.

---

## Key Features

- **Graphical User Interface**: A simple and modern interface built with Tkinter for ease of use.  
- **Smart Sync Filtering**: Filter downloads by a specific date range and select which technicians' reports to download, avoiding unnecessary API calls.  
- **Dual Download Modes**: Choose to download pixel-perfect PDF reports, attached photo evidence, or both simultaneously.  
- **High-Fidelity PDFs**: Generates perfect PDF copies of STS reports by using a headless Chrome browser to render the original web HTML and CSS.  
- **Concurrent Image Downloads**: Downloads associated report images in parallel using multiple workers for maximum speed.  
- **Automatic File Organization**: Automatically saves all files into a clean, categorized folder structure:  
  `[Output Folder]/[Technician Name]/[Client Name]/[STS Reports or Foto]/`.  
- **Download History**: Uses a local database to keep track of already downloaded files, preventing duplicates and allowing for fast incremental updates.  
- **External Configuration**: All settings, including credentials, output paths, and browser location, are stored in an easy-to-edit `config.ini` file.  
- **Robust Error Handling**: Catches and displays critical errors in a user-friendly way, preventing silent crashes.  

---

## Setup and Installation

Follow these steps to get the application running on your system.

### 1. Prerequisites
- **Python**: Ensure you have Python 3.10 or newer installed.  
- **Google Chrome**: The application requires Google Chrome to be installed for generating high-quality PDFs.  

### 2. Folder Structure

Create the following folder structure for the project:
```
pdf_downloader/
├── images/
│ ├── Logo MaxxGuard-1f60aee0.png
│ ├── Logo Primeshield-af83d41e.png
│ └── Logo ProServePlus-1ebed8c6.png
│ └── Logo_Secondary_ecoCare_Pest_Control-63c7d801.png
├── api/
│ ├── client.py
│ └── report_generator.py
├── database/
│ └── handler.py
├── gui/
│ └── app.py
├── main.py
├── config.ini
└── requirements.txt
```

### 3. Install Dependencies

Open a terminal or command prompt in the main `pdf_downloader` directory.  
Install the required Python libraries by running:

pip install -r requirements.txt

> **Note**: The first time you run this, the `pyppeteer` library may download a compatible version of the Chromium browser if it cannot find your local Chrome installation. This is a one-time setup and may take a few minutes.

---

## How to Use

1. **Configure**: Open the `config.ini` file and enter your PestCare username and password. It is also highly recommended to set the `chrome_executable_path`.  
2. **Run the Application**: Open your terminal in the project's root directory and run:  

python main.py

3. **Login**: The application window will appear. Click the **"Login & Fetch Technicians"** button. The app will authenticate with the API and populate the technician filter list.  
4. **Set Filters**:  
- Select the desired Date Range.  
- Uncheck any Technicians you wish to exclude.  
- Choose whether you want to download PDFs, Images, or both.  
5. **Start Download**: Click the **"Start Download"** button. The application will begin the *Smart Sync* process, and you can monitor the progress in the log window.  

---

## Configuration (`config.ini`)

All application settings are managed in the `config.ini` file.

- **username / password**: Your API login credentials.  
- **default_download_folder**: The main folder where all categorized subfolders will be created.  
- **max_workers**: The number of concurrent threads to use for downloading images.  
- **last_start_date / last_end_date**: The application remembers the last used date range.  
- **chrome_executable_path**: (Recommended) The full path to your installed `chrome.exe`. This prevents download issues and is more reliable. Use the *"Browser Settings..."* button in the app to set this easily.  
