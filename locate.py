import json
import os
import time
from tkinter import Tk, Canvas, Label, OptionMenu, StringVar
from PIL import Image, ImageTk
from pywifi import PyWiFi, const, Profile
import numpy as np
from collections import defaultdict
import math  # For distance calculation

class WiFiLocalization:
    def __init__(self, floorplan_image_path, ap_data_path="ap_locations.json", reference_distance=1, path_loss_exponent=4):
        self.ap_data = self.load_ap_data(ap_data_path)
        self.image_path = floorplan_image_path
        self.reference_distance = reference_distance  # Reference distance in meters (e.g., 1 meter)
        self.path_loss_exponent = path_loss_exponent  # Path loss exponent for the environment
        
        self.root = Tk()
        self.root.title("WiFi Localization")
        
        self.image = Image.open(floorplan_image_path)
        self.tk_image = ImageTk.PhotoImage(self.image)
        
        self.canvas = Canvas(self.root, width=self.image.width, height=self.image.height)
        self.canvas.pack()
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_image)
        
        self.user_location = None

        self.interface = None  # Selected interface
        self.interfaces = self.get_wifi_interfaces()
        self.selected_interface_var = StringVar(self.root)
        
        # Setup interface dropdown
        if self.interfaces:
            self.selected_interface_var.set(self.interfaces[0])  # Default selection
            self.interface_dropdown = OptionMenu(self.root, self.selected_interface_var, *self.interfaces, command=self.select_interface)
            self.interface_dropdown.pack()

    def load_ap_data(self, path):
        if os.path.exists(path):
            with open(path, "r") as file:
                return json.load(file)
        return []

    def get_wifi_interfaces(self):
        wifi = PyWiFi()
        interfaces = wifi.interfaces()
        interface_names = [iface.name() for iface in interfaces]
        return interface_names

    def select_interface(self, selected_interface):
        """Set the selected interface"""
        self.interface = selected_interface
        print(f"Selected Wi-Fi interface: {self.interface}")
    
    def scan_wifi(self):
        if not self.interface:
            print("No interface selected!")
            return []
        
        wifi = PyWiFi()
        iface = None
        
        # Find the selected interface
        for interface in wifi.interfaces():
            if interface.name() == self.interface:
                iface = interface
                break
        
        if iface is None:
            print("Interface not found!")
            return []

        # Force a fresh scan by manipulating the interface state
        current_profile = None
        if iface.status() in [const.IFACE_CONNECTED, const.IFACE_CONNECTING]:
            # Save current connection profile if connected
            try:
                current_profile = iface.network_profiles()[0]
            except:
                pass
            iface.disconnect()
            time.sleep(0.5)
            
        # Start scan
        iface.scan()
        time.sleep(2.5)  # Give more time for scan to complete
        scan_results = iface.scan_results()
        
        # Reconnect if we were connected previously
        if current_profile:
            iface.connect(current_profile)
        
        ap_list = []
        for ap in scan_results:
            ap_mac = ap.bssid.lower().replace(":", "")
            ap_list.append({
                    "mac": ap_mac,
                    "rssi": ap.signal
                })
        return ap_list

    def average_scans(self, num_scans=1):
        all_scans = []
        for _ in range(num_scans):
            all_scans.append(self.scan_wifi())
            
        ap_rssi_avg = defaultdict(list)
        for scan in all_scans:
            for ap in scan:
                ap_rssi_avg[ap['mac']].append(ap['rssi'])

        averaged_data = []
        for mac, rssi_list in ap_rssi_avg.items():
            averaged_data.append({
                "mac": mac,
                "rssi": int(np.median(rssi_list))
            })
        return averaged_data

    def rssi_to_distance(self, rssi):
        """
        Convert RSSI to distance using the path loss model.
        :param rssi: RSSI value (in dBm)
        :return: distance in meters
        """
        rssi_0 = -46  # Reference RSSI at 1 meter distance
        # Using the path loss model to calculate distance
        if rssi == 0:  # Avoid division by zero
            return float('inf')
        distance = self.reference_distance * 10 ** ((rssi_0 - rssi) / (10 * self.path_loss_exponent))
        return distance

    def estimate_location(self, scan_data):
        self.canvas.delete("ap_marker")
        self.canvas.delete("ap_label")
        self.canvas.delete("user")
        self.canvas.delete("arrow")

        ap_positions = []
        mac_labels = []
        weights = []
        
        max_rssi = -float('inf')
        strongest_ap_pos = None
        strongest_ap_mac = None

        for ap in scan_data:
            for known_ap in self.ap_data:
                known_mac = known_ap["id"].lower().replace(":", "")
                if ap["mac"] == known_mac:
                    current_rssi = ap["rssi"]
                    
                    # Convert RSSI to distance
                    distance = self.rssi_to_distance(current_rssi)
                    if distance == float('inf'):
                        continue  # Skip if the distance is invalid

                    ap_x = known_ap["x"] * self.image.width
                    ap_y = known_ap["y"] * self.image.height
                    
                    ap_positions.append((ap_x, ap_y))
                    mac_labels.append(known_ap["id"])
                    weights.append(1 / (distance ** 2))  # Inverse of the squared distance

                    break

        if not ap_positions:
            return None

        total_weight = sum(weights)
        weighted_x = sum(x * w for (x, y), w in zip(ap_positions, weights)) / total_weight
        weighted_y = sum(y * w for (x, y), w in zip(ap_positions, weights)) / total_weight

        # Optionally, draw AP markers based on the new weights (size of markers may also change)
        for (x, y), mac, weight in zip(ap_positions, mac_labels, weights):
            self.canvas.create_oval(
                x - 5, y - 5, x + 5, y + 5,
                fill="#ffdd00", outline="black", width=2,
                tags=("ap_marker",)
            )
            self.canvas.create_text(
                x, y + 5,
                text=mac,
                fill="black",
                anchor="n",
                font=("Arial", 8),
                tags=("ap_label",)
            )

        return weighted_x, weighted_y

    def plot_user_location(self, x, y):
        self.canvas.create_oval(
            x-10, y-10, x+10, y+10,
            fill="#0066ff", outline="white", width=2,
            tags=("user",)
        )

    def update_scan(self):
        # Use multiple scans for better consistency
        averaged_scan_data = self.average_scans(num_scans=3)
        
        if not averaged_scan_data:
            print("No Wi-Fi scan results found.")
        else:
            user_location = self.estimate_location(averaged_scan_data)
            if user_location:
                self.plot_user_location(*user_location)
            else:
                print("No matching APs found in scan data.")
        
        self.root.after(3000, self.update_scan)  # Longer interval to accommodate multiple scans

    def run(self):
        self.root.after(100, self.update_scan)
        self.root.mainloop()

if __name__ == "__main__":
    image_path = "plan.jpg"
    app = WiFiLocalization(image_path)
    app.run()
