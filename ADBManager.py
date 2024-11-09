import sys
import os
import subprocess
import logging
from google_play_scraper import app as fetch_app_details
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QListWidget, QListWidgetItem, 
    QPushButton, QMessageBox, QLabel, QHBoxLayout, QProgressDialog
)
from PyQt5.QtGui import QPixmap, QIcon, QFont
from PyQt5.QtCore import Qt, QSize, QTimer
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import contextlib

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Suppress console logs by redirecting stdout and stderr
@contextlib.contextmanager
def suppress_stdout_stderr():
    with open(os.devnull, 'w') as devnull:
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = devnull
        sys.stderr = devnull
        try:
            yield
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

class ADBManager(QWidget):
    def __init__(self):
        logging.info("Initializing ADBManager application.")
        super().__init__()
        self.setWindowTitle("ADB Manager")
        self.setGeometry(300, 100, 600, 500)
        self.setAcceptDrops(True)  # Enable drag-and-drop for this widget
        
        self.layout = QVBoxLayout()
        
        # List Widget to show installed apps
        self.app_list = QListWidget()
        self.app_list.setStyleSheet("background-color: #2e2e2e; color: white; border: none;")
        self.layout.addWidget(self.app_list)
        
        # Refresh button to reload the app list
        refresh_button = QPushButton("Refresh App List")
        refresh_button.setStyleSheet("""
            QPushButton {
                background-color: #3b3b3b;
                color: white;
                font-size: 14px;
                padding: 8px;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #555555;
            }
        """)
        refresh_button.clicked.connect(self.load_apps_with_progress)
        self.layout.addWidget(refresh_button)
        
        self.setLayout(self.layout)
        
        # Show progress bar and load apps on startup
        QTimer.singleShot(100, self.load_apps_with_progress)  # Delay to show window first

    def create_default_icon(self):
        """Create a default icon if default_icon.png does not exist."""
        default_icon_path = os.path.join(os.path.dirname(__file__), "default_icon.png")
        if not os.path.exists(default_icon_path):
            logging.info("Default icon not found. Generating default icon...")
            image = Image.new("RGBA", (64, 64), (100, 100, 100, 255))  # Gray background
            draw = ImageDraw.Draw(image)
            try:
                font = ImageFont.truetype("arial", 20)
            except IOError:
                logging.warning("Arial font not found. Using default font.")
                font = ImageFont.load_default()
            text = "APP"
            text_bbox = draw.textbbox((0, 0), text, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
            text_x = (image.width - text_width) // 2
            text_y = (image.height - text_height) // 2
            draw.text((text_x, text_y), text, fill=(255, 255, 255), font=font)
            image.save(default_icon_path)
            logging.info("Default icon generated and saved.")
        return default_icon_path

    def load_apps_with_progress(self):
        """Show progress bar and load apps."""
        logging.info("Loading apps with progress dialog.")
        self.progress_dialog = QProgressDialog("Loading apps...", "Cancel", 0, 0, self)
        self.progress_dialog.setWindowTitle("Please Wait")
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setMinimumDuration(500)  # Show after 0.5 seconds to avoid flicker
        self.progress_dialog.setValue(0)
        QTimer.singleShot(100, self.load_apps)  # Start loading apps in background

    def load_apps(self):
        """Load the list of installed apps with icons and names."""
        logging.info("Starting to load apps.")
        self.app_list.clear()

        # Check if ADB is connected (this will be silent due to suppression)
        with suppress_stdout_stderr():
            self.check_adb_connection()
        
        # Get the list of installed packages
        logging.info("Fetching list of installed packages via ADB.")
        process = subprocess.Popen(
            ["adb", "shell", "pm", "list", "packages", "-3"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        stdout, stderr = process.communicate()
        
        if stderr:
            logging.error("Error while loading apps: %s", stderr.decode())
            QMessageBox.critical(self, "Error", "Failed to load apps. Make sure ADB is running and the device is connected.")
            self.progress_dialog.cancel()
            return

        packages = stdout.decode().strip().splitlines()
        if not packages:
            logging.warning("No apps found or failed to retrieve the app list.")
            QMessageBox.warning(self, "Warning", "No apps found or failed to retrieve the app list.")
            self.progress_dialog.cancel()
            return

        for package_line in packages:
            package_name = package_line.split(":")[-1]
            logging.info("Adding app to list: %s", package_name)
            self.add_app_item(package_name)

        logging.info("Finished loading apps.")
        self.progress_dialog.close()

    def add_app_item(self, package_name):
        """Fetch app name and icon from Google Play, then add item to the list."""
        app_name = "No Name Found"
        
        # Load or generate default icon
        default_icon_path = self.create_default_icon()
        icon_pixmap = QPixmap(default_icon_path)
        icon_pixmap = icon_pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        
        try:
            app_details = fetch_app_details(package_name)
            app_name = app_details.get("title", app_name)
            icon_url = app_details.get("icon")
            if icon_url:
                logging.info("Fetching icon for %s", package_name)
                response = requests.get(icon_url)
                icon_pixmap = QPixmap()
                icon_pixmap.loadFromData(BytesIO(response.content).read())
                icon_pixmap = icon_pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        except Exception as e:
            logging.error("Failed to fetch details for %s: %s", package_name, e)

        # Set up the list item layout
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        
        icon_label = QLabel()
        icon_label.setPixmap(icon_pixmap)
        
        text_label = QLabel(f"{app_name} ({package_name})")
        text_label.setFont(QFont("Arial", 12))
        text_label.setStyleSheet("color: white; padding-left: 10px;")
        
        uninstall_button = QPushButton("Uninstall")
        uninstall_button.setStyleSheet("""
            QPushButton {
                background-color: #ff5555;
                color: white;
                font-size: 12px;
                padding: 6px 12px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #ff3333;
            }
        """)
        uninstall_button.setFixedSize(QSize(90, 30))
        uninstall_button.clicked.connect(lambda: self.uninstall_app(package_name))
        
        layout.addWidget(icon_label)
        layout.addWidget(text_label)
        layout.addStretch()
        layout.addWidget(uninstall_button)
        
        list_item = QListWidgetItem()
        list_item.setSizeHint(widget.sizeHint())
        self.app_list.addItem(list_item)
        self.app_list.setItemWidget(list_item, widget)
        logging.info("App %s added to list.", package_name)

    def uninstall_app(self, package_name):
        """Uninstall the selected app."""
        logging.info("Uninstalling app: %s", package_name)
        process = subprocess.run(["adb", "uninstall", package_name], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if process.returncode == 0:
            logging.info("App %s uninstalled successfully.", package_name)
        else:
            logging.error("Failed to uninstall app %s: %s", package_name, process.stderr.decode())
        
        self.load_apps_with_progress()

    def check_adb_connection(self):
        """Check ADB connection silently."""
        logging.info("Checking ADB connection.")
        process = subprocess.Popen(["adb", "devices"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        
        if "device" not in stdout.decode():
            logging.warning("No ADB device connected.")
            QMessageBox.critical(self, "Error", "No device connected. Please ensure your device is connected and ADB is enabled.")
            return
        logging.info("ADB device connected.")

    def dragEnterEvent(self, event):
        """Enable drag-and-drop for APK files."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
    
    def dropEvent(self, event):
        """Install APK when an APK file is dropped."""
        for url in event.mimeData().urls():
            apk_path = url.toLocalFile()
            if apk_path.endswith(".apk"):
                logging.info("APK dropped for installation: %s", apk_path)
                self.install_apk(apk_path)
    
    def install_apk(self, apk_path):
        """Install APK on the device."""
        reply = QMessageBox.question(
            self, "Install APK", f"Do you want to install {os.path.basename(apk_path)}?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            logging.info("Installing APK: %s", apk_path)
            process = subprocess.run(["adb", "install", apk_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if process.returncode == 0:
                logging.info("APK %s installed successfully.", apk_path)
                QMessageBox.information(self, "Success", f"{os.path.basename(apk_path)} installed successfully.")
            else:
                logging.error("Failed to install APK %s: %s", apk_path, process.stderr.decode())
                QMessageBox.critical(self, "Error", f"Failed to install {os.path.basename(apk_path)}.")
            self.load_apps_with_progress()

# Run the application
with suppress_stdout_stderr():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    manager = ADBManager()
    manager.show()
    sys.exit(app.exec_())
