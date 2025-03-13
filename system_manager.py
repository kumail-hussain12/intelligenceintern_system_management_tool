import os
import shutil
import time
import logging
import threading
import configparser
import smtplib
import socket
from datetime import datetime
from cryptography.fernet import Fernet
from email.mime.text import MIMEText
from tqdm import tqdm
import tkinter as tk
from tkinter import messagebox, filedialog
import schedule
import psutil

# ============================
# CONFIGURATION LOADING
# ============================

# Get the absolute path of config.ini
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.ini")

# Check if config.ini exists
if not os.path.exists(CONFIG_FILE):
    raise FileNotFoundError(f"Error: '{CONFIG_FILE}' not found. Ensure it exists in the same directory.")

# Read the config file
config = configparser.ConfigParser()
config.read(CONFIG_FILE)

# Validate required sections
required_sections = ["Email", "Backup"]
if not all(section in config for section in required_sections):
    raise ValueError(f"Error: Missing required sections {required_sections} in config.ini")

# Email Settings
EMAIL_SENDER = config.get("Email", "sender", fallback="")
EMAIL_RECEIVER = config.get("Email", "receiver", fallback="")
EMAIL_PASSWORD = config.get("Email", "password", fallback="")
SMTP_SERVER = config.get("Email", "smtp_server", fallback="smtp.gmail.com")
SMTP_PORT = config.getint("Email", "smtp_port", fallback=587)

# Backup Settings
SOURCE_DIR = config.get("Backup", "source_dir", fallback="")
BACKUP_DIR = config.get("Backup", "backup_dir", fallback="")
BACKUP_SCHEDULE = config.get("Backup", "backup_schedule", fallback="daily")

# ============================
# LOGGING & ENCRYPTION
# ============================

logging.basicConfig(filename="system_manager.log", level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Encryption Key (For Future Use)
key = Fernet.generate_key()
cipher = Fernet(key)

# ============================
# SYSTEM MONITORING
# ============================

def monitor_system():
    """Monitors CPU, Memory, and Disk usage."""
    while True:
        cpu_usage = psutil.cpu_percent(interval=1)
        memory_info = psutil.virtual_memory()
        disk_usage = psutil.disk_usage('/')
        logging.info(f"CPU: {cpu_usage}%, Memory: {memory_info.percent}%, Disk: {disk_usage.percent}%")
        time.sleep(5)

# ============================
# BACKUP FUNCTION
# ============================

def backup_files(source_dir, backup_dir):
    """Backs up files from source_dir to backup_dir with error handling."""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"backup_{timestamp}")
        os.makedirs(backup_path, exist_ok=True)

        files = os.listdir(source_dir)
        for file in tqdm(files, desc="Backing up files"):
            file_path = os.path.join(source_dir, file)
            if file.startswith('.'):  # Skip hidden files
                continue
            try:
                if os.path.isfile(file_path):
                    shutil.copy(file_path, backup_path)
                elif os.path.isdir(file_path):
                    shutil.copytree(file_path, os.path.join(backup_path, file))
            except PermissionError:
                logging.warning(f"Permission denied: {file_path}. Skipping...")
                continue

        logging.info(f"Backup successful: {backup_path}")
        send_email("Backup Completed", f"Backup completed successfully at {backup_path}")

    except Exception as e:
        logging.error(f"Backup failed: {e}")
        send_email("Backup Failed", f"Backup failed with error: {e}")

# ============================
# EMAIL NOTIFICATIONS
# ============================

def send_email(subject, body):
    """Sends email notifications for backup status."""
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = EMAIL_SENDER
        msg["To"] = EMAIL_RECEIVER

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())

        logging.info("Email notification sent successfully.")
    except smtplib.SMTPException as e:
        logging.error(f"Failed to send email: {e}")
    except socket.gaierror as e:
        logging.error(f"Failed to resolve SMTP server address: {e}")
    except Exception as e:
        logging.error(f"Unexpected error while sending email: {e}")

# ============================
# GUI FUNCTIONS
# ============================

def start_backup():
    """Starts the backup process."""
    source = source_entry.get()
    backup = backup_entry.get()
    if source and backup:
        threading.Thread(target=backup_files, args=(source, backup), daemon=True).start()
    else:
        messagebox.showerror("Error", "Please select source and backup directories.")

def select_source():
    """Selects the source directory."""
    source_entry.delete(0, tk.END)
    source_entry.insert(0, filedialog.askdirectory())

def select_backup():
    """Selects the backup directory."""
    backup_entry.delete(0, tk.END)
    backup_entry.insert(0, filedialog.askdirectory())

# ============================
# GUI CREATION
# ============================

def create_gui():
    """Creates a Tkinter GUI for backup selection."""
    global root, source_entry, backup_entry
    root = tk.Tk()
    root.title("System Management Tool")

    tk.Label(root, text="Source Directory:").grid(row=0, column=0, padx=10, pady=10)
    source_entry = tk.Entry(root, width=50)
    source_entry.grid(row=0, column=1, padx=10, pady=10)
    tk.Button(root, text="Browse", command=select_source).grid(row=0, column=2, padx=10, pady=10)

    tk.Label(root, text="Backup Directory:").grid(row=1, column=0, padx=10, pady=10)
    backup_entry = tk.Entry(root, width=50)
    backup_entry.grid(row=1, column=1, padx=10, pady=10)
    tk.Button(root, text="Browse", command=select_backup).grid(row=1, column=2, padx=10, pady=10)

    tk.Button(root, text="Start Backup", command=start_backup).grid(row=2, column=1, pady=20)

    root.mainloop()

# ============================
# BACKUP SCHEDULING
# ============================

if SOURCE_DIR and BACKUP_DIR:
    if BACKUP_SCHEDULE == "daily":
        schedule.every().day.at("02:00").do(backup_files, SOURCE_DIR, BACKUP_DIR)
    elif BACKUP_SCHEDULE == "weekly":
        schedule.every().week.do(backup_files, SOURCE_DIR, BACKUP_DIR)
else:
    logging.warning("Backup directories are not properly configured in config.ini.")

# ============================
# MAIN FUNCTION
# ============================

if __name__ == "__main__":
    threading.Thread(target=monitor_system, daemon=True).start()
    create_gui()
    while True:
        schedule.run_pending()
        time.sleep(1)
