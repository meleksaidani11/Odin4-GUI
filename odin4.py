import customtkinter as ctk
import subprocess
import threading
from tkinter import filedialog, messagebox
import serial.tools.list_ports
import time

class FlashToolApp:
    def __init__(self):
        self.root = ctk.CTk()
        self.root.geometry("800x510")
        self.root.title("Odin4 Download Tool")
        
        self.file_inputs = {
            "BL File": None,
            "AP File": None,
            "CP File": None,
            "CSC File": None,
            "UMS File": None,
        }

        self.create_ui()

        self.device_thread = threading.Thread(target=self.detect_devices_periodically, daemon=True)
        self.device_thread.start()

    def create_ui(self):
        title_label = ctk.CTkLabel(self.root, text="Odin4 Download Tool", font=("Arial", 18, "bold"))
        title_label.pack(pady=10)

        com_frame = ctk.CTkFrame(self.root)
        com_frame.pack(pady=20)

        self.com_label = ctk.CTkLabel(com_frame, text="Device (COM Port):", font=("Arial", 12))
        self.com_label.pack(side="left", padx=10)

        self.com_dropdown = ctk.CTkComboBox(com_frame, values=["No device detected"], width=300, height=30)
        self.com_dropdown.pack(side="left", padx=12)

        files_frame = ctk.CTkFrame(self.root)
        files_frame.pack(pady=20)

        for label in self.file_inputs:
            self.create_file_input(label, files_frame)

        options_frame = ctk.CTkFrame(self.root)
        options_frame.pack(pady=10)

        self.nand_erase_var = ctk.BooleanVar()
        self.reboot_var = ctk.BooleanVar(value=False)

        ctk.CTkCheckBox(options_frame, text="NAND Erase", variable=self.nand_erase_var, font=("Arial", 12)).pack(side="left", padx=10)
        ctk.CTkCheckBox(options_frame, text="Reboot After Flash", variable=self.reboot_var, font=("Arial", 12)).pack(side="left", padx=10)

        flash_button = ctk.CTkButton(options_frame, text="Flash", command=self.start_flashing, width=200)
        flash_button.pack(side="left", padx=10)

        progress_frame = ctk.CTkFrame(self.root)
        progress_frame.pack(pady=10)

        self.progress_label = ctk.CTkLabel(progress_frame, text="Progress:", font=("Arial", 14))
        self.progress_label.pack(side="left", padx=10)

        self.progress_bar = ctk.CTkProgressBar(progress_frame, width=300)
        self.progress_bar.pack(side="left", padx=10)
        self.progress_bar.set(0)

        info_frame = ctk.CTkFrame(self.root)
        info_frame.pack(pady=10)

        self.remaining_time_label = ctk.CTkLabel(info_frame, text="Time Remaining: 00:00", font=("Arial", 12))
        self.remaining_time_label.pack(side="left", padx=10)

        self.current_file_label = ctk.CTkLabel(info_frame, text="Current File: None", font=("Arial", 12))
        self.current_file_label.pack(side="left", padx=10)

    def create_file_input(self, label, parent_frame):
        frame = ctk.CTkFrame(parent_frame)
        frame.pack(pady=5, fill="x", padx=20)

        label_widget = ctk.CTkLabel(frame, text=label, anchor="w", font=("Arial", 12))
        label_widget.pack(side="left", padx=10)

        entry = ctk.CTkEntry(frame, width=300, height=30)
        entry.pack(side="left", padx=10)

        button = ctk.CTkButton(frame, text="Browse", command=lambda: self.browse_file(entry), width=100)
        button.pack(side="left", padx=10)

        self.file_inputs[label] = entry

    def browse_file(self, entry):
        file_path = filedialog.askopenfilename(filetypes=[("All Files", "*.*")])
        if file_path:
            entry.delete(0, "end")
            entry.insert(0, file_path)

    def detect_devices(self):
        try:
            ports = serial.tools.list_ports.comports()
            devices = []

            for port in ports:
                device_info = f"{port.device} - {port.description}"
                devices.append(device_info)

            if devices:
                self.com_dropdown.configure(values=devices)
                self.com_dropdown.set(devices[0])
            else:
                self.com_dropdown.configure(values=["No device detected"])
                self.com_dropdown.set("No device detected")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to detect devices: {e}")

    def detect_devices_periodically(self):
        while True:
            self.detect_devices()
            time.sleep(2)

    def start_flashing(self):
        threading.Thread(target=self.flash_device).start()

    def flash_device(self):
        selected_device = self.com_dropdown.get()
        if selected_device == "No device detected":
            messagebox.showerror("Error", "No device selected!")
            return

        com_port = selected_device.split(" - ")[0]

        flash_files = []
        for label, entry in self.file_inputs.items():
            file_path = entry.get()
            if file_path:
                flash_files.append((label, file_path))

        total_files = len(flash_files)
        if total_files == 0:
            messagebox.showerror("Error", "No files selected for flashing!")
            return

        self.progress_bar.set(0)
        progress_step = 1 / total_files

        try:
            for i, (label, file_path) in enumerate(flash_files):
                self.current_file_label.configure(text=f"Current File: {label} ({file_path})")
                command = ["Odin/odin", "-a", file_path, "-d", com_port]
                subprocess.run(command, check=True)

                remaining_time = (total_files - i - 1) * 5
                minutes = remaining_time // 60
                seconds = remaining_time % 60
                self.remaining_time_label.configure(text=f"Time Remaining: {minutes:02}:{seconds:02}")

                self.progress_bar.set(progress_step * (i + 1))
                time.sleep(2)

            if self.reboot_var.get():
                reboot_command = ["Odin/odin", "-d", com_port, "--reboot"]
                subprocess.run(reboot_command, check=True)

            messagebox.showinfo("Success", "Flashing completed successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Flashing failed: {e}")

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = FlashToolApp()
    app.run()
