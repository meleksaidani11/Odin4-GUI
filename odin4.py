import sys
import subprocess
import threading
import time
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QLabel, QComboBox, QPushButton,
    QFileDialog, QMessageBox, QProgressBar, QCheckBox, QVBoxLayout,
    QHBoxLayout, QWidget, QFrame, QLineEdit  
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
import serial.tools.list_ports

class FlashToolApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Odin4 Download Tool")
        self.setGeometry(100, 100, 800, 510)

        self.file_inputs = {
            "BL File": None,
            "AP File": None,
            "CP File": None,
            "CSC File": None,
            "UMS File": None,
        }

        self.init_ui()

        self.device_thread = threading.Thread(target=self.detect_devices_periodically, daemon=True)
        self.device_thread.start()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        title_label = QLabel("Odin4 Download Tool")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title_label, alignment=Qt.AlignCenter)

        com_frame = QFrame()
        com_layout = QHBoxLayout(com_frame)
        self.com_label = QLabel("Device (COM Port):")
        self.com_dropdown = QComboBox()
        self.com_dropdown.addItem("No device detected")
        self.com_dropdown.setFixedWidth(300)
        com_layout.addWidget(self.com_label)
        com_layout.addWidget(self.com_dropdown)
        layout.addWidget(com_frame)

        files_frame = QFrame()
        files_layout = QVBoxLayout(files_frame)
        for label in self.file_inputs:
            self.create_file_input(label, files_layout)
        layout.addWidget(files_frame)

        options_frame = QFrame()
        options_layout = QHBoxLayout(options_frame)
        self.nand_erase_var = QCheckBox("NAND Erase")
        self.reboot_var = QCheckBox("Reboot After Flash")
        self.reboot_var.setChecked(True)
        options_layout.addWidget(self.nand_erase_var)
        options_layout.addWidget(self.reboot_var)
        flash_button = QPushButton("Flash")
        flash_button.clicked.connect(self.start_flashing)
        flash_button.setFixedWidth(200)
        options_layout.addWidget(flash_button)
        layout.addWidget(options_frame)

        progress_frame = QFrame()
        progress_layout = QHBoxLayout(progress_frame)
        self.progress_label = QLabel("Progress:")
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedWidth(300)
        progress_layout.addWidget(self.progress_label)
        progress_layout.addWidget(self.progress_bar)
        layout.addWidget(progress_frame)

        info_frame = QFrame()
        info_layout = QHBoxLayout(info_frame)
        self.remaining_time_label = QLabel("Time Remaining: 00:00")
        self.current_file_label = QLabel("Current File: None")
        info_layout.addWidget(self.remaining_time_label)
        info_layout.addWidget(self.current_file_label)
        layout.addWidget(info_frame)

    def create_file_input(self, label, parent_layout):
        frame = QFrame()
        frame_layout = QHBoxLayout(frame)
        label_widget = QLabel(label)
        entry = QLineEdit()
        entry.setFixedWidth(300)
        browse_button = QPushButton("Browse")
        browse_button.clicked.connect(lambda: self.browse_file(entry))
        frame_layout.addWidget(label_widget)
        frame_layout.addWidget(entry)
        frame_layout.addWidget(browse_button)
        parent_layout.addWidget(frame)
        self.file_inputs[label] = entry

    def browse_file(self, entry):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select File", "", "All Files (*.*)")
        if file_path:
            entry.setText(file_path)

    def detect_devices(self):
        try:
            ports = serial.tools.list_ports.comports()
            devices = []

            for port in ports:
                device_info = f"{port.device} - {port.description}"
                devices.append(device_info)

            if devices:
                self.com_dropdown.clear()
                self.com_dropdown.addItems(devices)
            else:
                self.com_dropdown.clear()
                self.com_dropdown.addItem("No device detected")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to detect devices: {e}")

    def detect_devices_periodically(self):
        while True:
            self.detect_devices()
            time.sleep(2)

    def start_flashing(self):
        self.flash_thread = FlashThread(self)
        self.flash_thread.finished.connect(self.on_flash_finished)
        self.flash_thread.start()

    def on_flash_finished(self, success, message):
        if success:
            QMessageBox.information(self, "Success", message)
        else:
            QMessageBox.critical(self, "Error", message)

class FlashThread(QThread):
    finished = pyqtSignal(bool, str)

    def __init__(self, parent):
        super().__init__()
        self.parent = parent

    def run(self):
        selected_device = self.parent.com_dropdown.currentText()
        if selected_device == "No device detected":
            self.finished.emit(False, "No device selected!")
            return

        com_port = selected_device.split(" - ")[0]

        flash_files = []
        for label, entry in self.parent.file_inputs.items():
            file_path = entry.text()
            if file_path:
                flash_files.append((label, file_path))

        total_files = len(flash_files)
        if total_files == 0:
            self.finished.emit(False, "No files selected for flashing!")
            return

        self.parent.progress_bar.setValue(0)
        progress_step = 100 / total_files

        try:
            for i, (label, file_path) in enumerate(flash_files):
                self.parent.current_file_label.setText(f"Current File: {label} ({file_path})")
                command = ["Odin/odin", "-a", file_path, "-d", com_port]
                subprocess.run(command, check=True)

                remaining_time = (total_files - i - 1) * 5
                minutes = remaining_time // 60
                seconds = remaining_time % 60
                self.parent.remaining_time_label.setText(f"Time Remaining: {minutes:02}:{seconds:02}")

                
                self.parent.progress_bar.setValue(int(progress_step * (i + 1)))
                time.sleep(2)

            
            if self.parent.reboot_var.isChecked():
                print("Executing reboot command...")
                reboot_command = ["Odin/odin", "-d", com_port, "--reboot"]
                subprocess.run(reboot_command, check=True)
            else:
                print("Reboot skipped. Device not restarted.")

           
            time.sleep(5)  # 
            print("Connection closed.")

            self.finished.emit(True, "Flashing completed successfully!")
        except Exception as e:
            self.finished.emit(False, f"Flashing failed: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FlashToolApp()
    window.show()
    sys.exit(app.exec_())
