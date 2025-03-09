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
import hashlib

# Configuration
config = configparser.ConfigParser()
config.read("config.ini")

# Logging
logging.basicConfig(filename="system_manager.log", level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Encryption
key = Fernet.generate_key()
cipher = Fernet(key)

# Email Settings
EMAIL_SENDER = config.get("Email", "sender")
EMAIL_RECEIVER = config.get("Email", "receiver")
EMAIL_PASSWORD = config.get("Email", "password")
SMTP_SERVER = config.get("Email", "smtp_server")
SMTP_PORT = config.getint("Email", "smtp_port")

# Backup Settings
SOURCE_DIR = config.get("Backup", "source_dir")
BACKUP_DIR = config.get("Backup", "backup_dir")
BACKUP_SCHEDULE = config.get("Backup", "backup_schedule")

# System Monitoring
def monitor_system():
    while True:
        cpu_usage = psutil.cpu_percent(interval=1)
        memory_info = psutil.virtual_memory()
        disk_usage = psutil.disk_usage('/')
        network_info = psutil.net_io_counters()
        logging.info(f"CPU Usage: {cpu_usage}%, Memory Usage: {memory_info.percent}%, Disk Usage: {disk_usage.percent}%")
        time.sleep(5)

# File Backup
def backup_files(source_dir, backup_dir):
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"backup_{timestamp}")
        os.makedirs(backup_path, exist_ok=True)

        files = os.listdir(source_dir)
        for file in tqdm(files, desc="Backing up files"):
            file_path = os.path.join(source_dir, file)
            # Skip hidden files/directories (e.g., .git, .DS_Store)
            if file.startswith('.'):
                logging.info(f"Skipping hidden file/directory: {file_path}")
                continue
            try:
                if os.path.isfile(file_path):
                    shutil.copy(file_path, backup_path)
                elif os.path.isdir(file_path):
                    shutil.copytree(file_path, os.path.join(backup_path, file))
            except PermissionError as e:
                logging.warning(f"Permission denied: {file_path}. Skipping...")
                continue

        logging.info(f"Backup successful: {backup_path}")
        send_email("Backup Completed", f"Backup completed successfully at {backup_path}")
    except Exception as e:
        logging.error(f"Backup failed: {e}")
        send_email("Backup Failed", f"Backup failed with error: {e}")

# Email Notifications
def send_email(subject, body):
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

# GUI Functions
def start_backup():
    source = source_entry.get()
    backup = backup_entry.get()
    if source and backup:
        threading.Thread(target=backup_files, args=(source, backup)).start()
    else:
        messagebox.showerror("Error", "Please select source and backup directories.")

def select_source():
    source_entry.delete(0, tk.END)
    source_entry.insert(0, filedialog.askdirectory())

def select_backup():
    backup_entry.delete(0, tk.END)
    backup_entry.insert(0, filedialog.askdirectory())

# Create the main window
def create_gui():
    global root, source_entry, backup_entry
    root = tk.Tk()
    root.title("System Management Tool")

    # Source Directory
    tk.Label(root, text="Source Directory:").grid(row=0, column=0, padx=10, pady=10)
    source_entry = tk.Entry(root, width=50)
    source_entry.grid(row=0, column=1, padx=10, pady=10)
    tk.Button(root, text="Browse", command=select_source).grid(row=0, column=2, padx=10, pady=10)

    # Backup Directory
    tk.Label(root, text="Backup Directory:").grid(row=1, column=0, padx=10, pady=10)
    backup_entry = tk.Entry(root, width=50)
    backup_entry.grid(row=1, column=1, padx=10, pady=10)
    tk.Button(root, text="Browse", command=select_backup).grid(row=1, column=2, padx=10, pady=10)

    # Start Backup Button
    tk.Button(root, text="Start Backup", command=start_backup).grid(row=2, column=1, pady=20)

    # Run the GUI main loop
    root.mainloop()

# Schedule Backups
if BACKUP_SCHEDULE == "daily":
    schedule.every().day.at("02:00").do(backup_files, SOURCE_DIR, BACKUP_DIR)
elif BACKUP_SCHEDULE == "weekly":
    schedule.every().week.do(backup_files, SOURCE_DIR, BACKUP_DIR)

# Main Function
if __name__ == "__main__":
    # Start system monitoring in a separate thread
    threading.Thread(target=monitor_system, daemon=True).start()

    # Start the GUI in the main thread
    create_gui()

    # Run the scheduler in the main thread
    while True:
        schedule.run_pending()
        time.sleep(1)