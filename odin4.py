import sys
import subprocess
import threading
import time
import os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QLabel, QComboBox, QPushButton,
    QFileDialog, QMessageBox, QProgressBar, QCheckBox, QVBoxLayout,
    QHBoxLayout, QWidget, QFrame, QLineEdit, QGridLayout, QGroupBox,
    QSplitter, QTabWidget, QScrollArea, QSpacerItem, QSizePolicy, QStatusBar
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QIcon, QPixmap, QFont, QColor, QPalette, QCursor, QFontDatabase
import serial.tools.list_ports

class AnimatedProgressBar(QProgressBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimum(0)
        self.setMaximum(100)
        self.setValue(0)
        self.setTextVisible(True)
        self.setFixedHeight(20)
        self.setStyleSheet("""
            QProgressBar {
                border: 1px solid #555;
                border-radius: 10px;
                background-color: #2E2E2E;
                color: white;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0078D7, stop:1 #00AEFF);
                border-radius: 10px;
            }
        """)

class StyledButton(QPushButton):
    def __init__(self, text, parent=None, primary=False):
        super().__init__(text, parent)
        self.primary = primary
        self.setMinimumHeight(36)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.update_style()
    
    def update_style(self):
        if self.primary:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #0078D7;
                    color: white;
                    border: none;
                    border-radius: 5px;
                    padding: 8px 16px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #0086F0;
                }
                QPushButton:pressed {
                    background-color: #005FA3;
                }
                QPushButton:disabled {
                    background-color: #555555;
                    color: #999999;
                }
            """)
        else:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #3A3A3A;
                    color: white;
                    border: 1px solid #555555;
                    border-radius: 5px;
                    padding: 8px 16px;
                }
                QPushButton:hover {
                    background-color: #454545;
                    border: 1px solid #666666;
                }
                QPushButton:pressed {
                    background-color: #2A2A2A;
                }
                QPushButton:disabled {
                    background-color: #2A2A2A;
                    color: #555555;
                    border: 1px solid #444444;
                }
            """)

class FileSelectWidget(QWidget):
    def __init__(self, label, parent=None):
        super().__init__(parent)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.label = QLabel(label)
        self.label.setMinimumWidth(80)
        
        self.entry = QLineEdit()
        self.entry.setPlaceholderText(f"Select {label} file...")
        self.entry.setStyleSheet("""
            QLineEdit {
                border: 1px solid #555;
                border-radius: 5px;
                padding: 8px;
                background-color: #2A2A2A;
                color: white;
            }
            QLineEdit:focus {
                border: 1px solid #0078D7;
            }
        """)
        
        self.browse_button = StyledButton("Browse")
        self.browse_button.setIcon(QIcon.fromTheme("folder-open"))
        
        self.layout.addWidget(self.label)
        self.layout.addWidget(self.entry, 1)
        self.layout.addWidget(self.browse_button)
        
        self.browse_button.clicked.connect(self.browse_file)
    
    def browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, f"Select {self.label} File", "", "All Files (*.*)")
        if file_path:
            self.entry.setText(file_path)
            original_style = self.entry.styleSheet()
            self.entry.setStyleSheet("""
                QLineEdit {
                    border: 1px solid #00AA00;
                    border-radius: 5px;
                    padding: 8px;
                    background-color: #2A2A2A;
                    color: white;
                }
            """)
            QTimer.singleShot(300, lambda: self.entry.setStyleSheet(original_style))
    
    def get_file_path(self):
        return self.entry.text()
    
    def set_file_path(self, path):
        self.entry.setText(path)

class DeviceMonitor(QThread):
    device_updated = pyqtSignal(list)
    
    def run(self):
        while True:
            try:
                ports = serial.tools.list_ports.comports()
                devices = []
                for port in ports:
                    device_info = f"{port.device} - {port.description}"
                    devices.append((port.device, device_info))
                self.device_updated.emit(devices)
            except Exception as e:
                print(f"Error detecting devices: {e}")
            time.sleep(2)

class FlashThread(QThread):
    progress_updated = pyqtSignal(int, str, str)
    finished = pyqtSignal(bool, str)
    
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.files_to_flash = []
        self.com_port = ""
        self.reboot = False
        self.nand_erase = False
        self.odin_path = "Odin/odin.exe"  # تعديل المسار حسب موقع Odin على جهازك
        
    def configure(self, com_port, files_to_flash, reboot, nand_erase):
        self.com_port = com_port
        self.files_to_flash = files_to_flash
        self.reboot = reboot
        self.nand_erase = nand_erase
        
    def run(self):
        if not self.com_port or self.com_port == "No device detected":
            self.finished.emit(False, "No device selected!")
            return
            
        if not self.files_to_flash:
            self.finished.emit(False, "No files selected for flashing!")
            return
        
        total_files = len(self.files_to_flash)
        progress_step = 90 / total_files if total_files > 0 else 0  # 90% للتفليش، 10% للإعداد/الإعادة
        
        try:
            # مسح NAND إذا تم تحديده
            if self.nand_erase:
                self.progress_updated.emit(0, "Preparing NAND Erase", "Calculating...")
                command = [self.odin_path, "-d", self.com_port, "--nand-erase"]
                self.progress_updated.emit(5, "Performing NAND Erase", "In progress...")
                subprocess.run(command, check=True, capture_output=True, text=True)
                self.progress_updated.emit(10, "NAND Erase Completed", "00:00")
                
            # تفليش كل ملف
            for i, (label, file_path) in enumerate(self.files_to_flash):
                file_name = os.path.basename(file_path)
                base_progress = 10 + int(progress_step * i)
                self.progress_updated.emit(
                    base_progress,
                    f"Flashing: {label} ({file_name})",
                    "In progress..."
                )
                
                # افتراض وسائط Odin (قد تحتاج تعديلها حسب النسخة)
                command = [self.odin_path, "-a", file_path, "-d", self.com_port]
                process = subprocess.run(command, check=True, capture_output=True, text=True)
                
                self.progress_updated.emit(
                    base_progress + int(progress_step),
                    f"Flashed: {label} ({file_name})",
                    "00:00"
                )
            
            # إعادة تشغيل الجهاز إذا تم تحديده
            if self.reboot:
                self.progress_updated.emit(95, "Rebooting device", "In progress...")
                reboot_command = [self.odin_path, "-d", self.com_port, "--reboot"]
                subprocess.run(reboot_command, check=True, capture_output=True, text=True)
            
            self.progress_updated.emit(100, "Operation completed successfully", "00:00")
            self.finished.emit(True, "Flashing completed successfully!")
            
        except subprocess.CalledProcessError as e:
            error_msg = f"Flashing failed: {e.stderr}"
            self.finished.emit(False, error_msg)
        except Exception as e:
            self.finished.emit(False, f"Flashing failed: {str(e)}")

class FlashToolApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Samsung Odin4 Professional Flash Tool")
        self.setGeometry(100, 100, 900, 600)
        self.setMinimumSize(800, 500)
        
        self.apply_dark_theme()
        self.init_ui()
        
        self.device_monitor = DeviceMonitor()
        self.device_monitor.device_updated.connect(self.update_device_list)
        self.device_monitor.start()
        
        self.flash_thread = FlashThread(self)
        self.flash_thread.progress_updated.connect(self.update_progress)
        self.flash_thread.finished.connect(self.on_flash_finished)
        
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(5000)
    
    def apply_dark_theme(self):
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #1E1E1E;
                color: #FFFFFF;
                font-family: 'Segoe UI', 'Arial', sans-serif;
            }
            QLabel {
                color: #CCCCCC;
            }
            QGroupBox {
                border: 1px solid #555555;
                border-radius: 5px;
                margin-top: 1ex;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 5px;
                color: #0078D7;
            }
            QTabWidget::pane {
                border: 1px solid #555555;
                border-radius: 5px;
            }
            QTabBar::tab {
                background-color: #2D2D2D;
                color: #CCCCCC;
                padding: 8px 16px;
                border: 1px solid #555555;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: #3D3D3D;
                color: #FFFFFF;
                border-bottom: none;
            }
            QTabBar::tab:hover:!selected {
                background-color: #353535;
            }
            QComboBox {
                border: 1px solid #555555;
                border-radius: 5px;
                padding: 5px 10px;
                background-color: #2A2A2A;
                color: white;
                min-height: 25px;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 15px;
                border-left: 1px solid #555555;
            }
            QCheckBox {
                spacing: 5px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QCheckBox::indicator:unchecked {
                border: 1px solid #555555;
                background-color: #2A2A2A;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                border: 1px solid #0078D7;
                background-color: #0078D7;
                border-radius: 3px;
            }
            QStatusBar {
                background-color: #2A2A2A;
                color: #AAAAAA;
            }
            QMenuBar {
                background-color: #2A2A2A;
                color: white;
            }
            QMenuBar::item:selected {
                background-color: #0078D7;
            }
        """)
    
    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        header_layout = QHBoxLayout()
        logo_label = QLabel("ODIN4")
        logo_label.setStyleSheet("font-size: 28px; font-weight: bold; color: #0078D7;")
        header_layout.addWidget(logo_label)
        
        title_label = QLabel("Professional Firmware Flash Tool")
        title_label.setStyleSheet("font-size: 22px; font-weight: bold; color: #CCCCCC;")
        header_layout.addWidget(title_label)
        header_layout.addStretch(1)
        
        device_group = QGroupBox("Device Connection")
        device_layout = QGridLayout(device_group)
        
        self.com_label = QLabel("Target Device:")
        self.com_dropdown = QComboBox()
        self.com_dropdown.setMinimumWidth(350)
        self.com_dropdown.addItem("No device detected")
        self.com_dropdown.setCurrentIndex(0)
        
        self.refresh_button = StyledButton("Refresh")
        self.refresh_button.setIcon(QIcon.fromTheme("view-refresh"))
        self.refresh_button.clicked.connect(self.refresh_devices)
        
        device_layout.addWidget(self.com_label, 0, 0)
        device_layout.addWidget(self.com_dropdown, 0, 1)
        device_layout.addWidget(self.refresh_button, 0, 2)
        
        self.device_status = QLabel("Device Status: Not Connected")
        self.device_status.setStyleSheet("color: #FF5555;")
        device_layout.addWidget(self.device_status, 1, 0, 1, 3)
        
        files_tabs = QTabWidget()
        standard_tab = QWidget()
        standard_layout = QVBoxLayout(standard_tab)
        
        self.file_widgets = {}
        file_types = ["BL File", "AP File", "CP File", "CSC File", "UMS File"]
        
        for file_type in file_types:
            file_widget = FileSelectWidget(file_type)
            self.file_widgets[file_type] = file_widget
            standard_layout.addWidget(file_widget)
        
        standard_layout.addStretch(1)
        files_tabs.addTab(standard_tab, "Standard Flash")
        
        advanced_tab = QWidget()
        advanced_layout = QVBoxLayout(advanced_tab)
        advanced_layout.addWidget(QLabel("Advanced flashing options will be available in future updates."))
        advanced_layout.addStretch(1)
        files_tabs.addTab(advanced_tab, "Advanced Mode")
        
        options_group = QGroupBox("Flash Options")
        options_layout = QGridLayout(options_group)
        
        self.nand_erase_checkbox = QCheckBox("NAND Erase All")
        self.nand_erase_checkbox.setToolTip("Erase NAND memory before flashing. Warning: Will erase all data!")
        
        self.reboot_checkbox = QCheckBox("Auto Reboot")
        self.reboot_checkbox.setChecked(True)
        self.reboot_checkbox.setToolTip("Automatically reboot device after flashing is complete")
        
        self.backup_checkbox = QCheckBox("Backup EFS")
        self.backup_checkbox.setToolTip("Create a backup of EFS partition before flashing (recommended)")
        
        options_layout.addWidget(self.nand_erase_checkbox, 0, 0)
        options_layout.addWidget(self.reboot_checkbox, 0, 1)
        options_layout.addWidget(self.backup_checkbox, 1, 0)
        
        buttons_layout = QHBoxLayout()
        
        self.flash_button = StyledButton("Start Flashing", primary=True)
        self.flash_button.setIcon(QIcon.fromTheme("system-run"))
        self.flash_button.clicked.connect(self.start_flashing)
        
        self.cancel_button = StyledButton("Cancel")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel_flashing)
        
        buttons_layout.addStretch(1)
        buttons_layout.addWidget(self.cancel_button)
        buttons_layout.addWidget(self.flash_button)
        
        progress_group = QGroupBox("Operation Progress")
        progress_layout = QVBoxLayout(progress_group)
        
        progress_info_layout = QHBoxLayout()
        
        self.current_operation_label = QLabel("Ready")
        self.remaining_time_label = QLabel("Time Remaining: --:--")
        self.remaining_time_label.setAlignment(Qt.AlignRight)
        
        progress_info_layout.addWidget(self.current_operation_label)
        progress_info_layout.addStretch(1)
        progress_info_layout.addWidget(self.remaining_time_label)
        
        self.progress_bar = AnimatedProgressBar()
        
        progress_layout.addLayout(progress_info_layout)
        progress_layout.addWidget(self.progress_bar)
        
        main_layout.addLayout(header_layout)
        main_layout.addWidget(device_group)
        main_layout.addWidget(files_tabs, 1)
        main_layout.addWidget(options_group)
        main_layout.addLayout(buttons_layout)
        main_layout.addWidget(progress_group)
        
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("Ready")
        self.setStatusBar(self.status_bar)
    
    def update_device_list(self, devices):
        current_device = self.com_dropdown.currentText()
        self.com_dropdown.clear()
        
        if devices:
            for device_id, device_info in devices:
                self.com_dropdown.addItem(device_info)
            
            if current_device in [info for _, info in devices]:
                self.com_dropdown.setCurrentText(current_device)
            
            self.device_status.setText("Device Status: Connected")
            self.device_status.setStyleSheet("color: #55FF55;")
        else:
            self.com_dropdown.addItem("No device detected")
            self.device_status.setText("Device Status: Not Connected")
            self.device_status.setStyleSheet("color: #FF5555;")
    
    def refresh_devices(self):
        self.refresh_button.setEnabled(False)
        self.refresh_button.setText("Scanning...")
        
        if hasattr(self, 'device_monitor'):
            ports = serial.tools.list_ports.comports()
            devices = []
            for port in ports:
                device_info = f"{port.device} - {port.description}"
                devices.append((port.device, device_info))
            self.update_device_list(devices)
        
        QTimer.singleShot(1000, lambda: self.reset_refresh_button())
    
    def reset_refresh_button(self):
        self.refresh_button.setText("Refresh")
        self.refresh_button.setEnabled(True)
    
    def start_flashing(self):
        selected_device = self.com_dropdown.currentText()
        if selected_device == "No device detected":
            QMessageBox.warning(self, "No Device", "No device selected! Please connect a device.")
            return
        
        com_port = selected_device.split(" - ")[0]
        
        files_to_flash = []
        for label, widget in self.file_widgets.items():
            file_path = widget.get_file_path()
            if file_path:
                files_to_flash.append((label, file_path))
        
        if not files_to_flash:
            QMessageBox.warning(self, "No Files", "No files selected for flashing!")
            return
        
        message = f"Ready to flash {len(files_to_flash)} file(s) to device {com_port}.\n\n"
        if self.nand_erase_checkbox.isChecked():
            message += "WARNING: NAND Erase is enabled. This will erase all data on the device!\n\n"
        
        message += "Do you want to continue?"
        
        reply = QMessageBox.question(self, "Confirm Flash Operation", 
                                     message, QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.No:
            return
        
        self.flash_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.com_dropdown.setEnabled(False)
        for widget in self.file_widgets.values():
            widget.browse_button.setEnabled(False)
            widget.entry.setEnabled(False)
        
        self.progress_bar.setValue(0)
        self.current_operation_label.setText("Initializing...")
        self.remaining_time_label.setText("Preparing...")
        
        self.flash_thread.configure(
            com_port,
            files_to_flash,
            self.reboot_checkbox.isChecked(),
            self.nand_erase_checkbox.isChecked()
        )
        self.flash_thread.start()
    
    def update_progress(self, progress, operation, time_remaining):
        self.progress_bar.setValue(progress)
        self.current_operation_label.setText(operation)
        self.remaining_time_label.setText(f"Time Remaining: {time_remaining}")
        self.status_bar.showMessage(f"{operation} - {progress}% complete")
    
    def cancel_flashing(self):
        if self.flash_thread.isRunning():
            reply = QMessageBox.question(self, "Cancel Operation", 
                                        "Are you sure you want to cancel the current operation?\nThis may leave your device in an unstable state.",
                                        QMessageBox.Yes | QMessageBox.No)
            
            if reply == QMessageBox.Yes:
                self.flash_thread.terminate()
                self.on_flash_finished(False, "Operation cancelled by user.")
    
    def on_flash_finished(self, success, message):
        self.flash_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.com_dropdown.setEnabled(True)
        for widget in self.file_widgets.values():
            widget.browse_button.setEnabled(True)
            widget.entry.setEnabled(True)
        
        if success:
            self.status_bar.showMessage("Operation completed successfully")
            QMessageBox.information(self, "Success", message)
        else:
            self.status_bar.showMessage("Operation failed")
            QMessageBox.critical(self, "Error", message)
        
        self.current_operation_label.setText("Ready")
        self.remaining_time_label.setText("Time Remaining: --:--")
    
    def update_status(self):
        if not self.flash_thread.isRunning():
            device = self.com_dropdown.currentText()
            if device != "No device detected":
                self.status_bar.showMessage(f"Connected to {device} - Ready")
            else:
                self.status_bar.showMessage("No device connected - Please connect a device")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FlashToolApp()
    window.show()
    sys.exit(app.exec_())
