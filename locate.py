import json
import os
import time
from tkinter import Tk, Canvas
from PIL import Image, ImageTk
from pywifi import PyWiFi, const, Profile
import numpy as np
from collections import defaultdict

class WiFiLocalization:
    def __init__(self, floorplan_image_path, ap_data_path="ap_locations.json"):
        self.ap_data = self.load_ap_data(ap_data_path)
        self.image_path = floorplan_image_path
        
        self.root = Tk()
        self.root.title("WiFi Localization")
        
        self.image = Image.open(floorplan_image_path)
        self.tk_image = ImageTk.PhotoImage(self.image)
        
        self.canvas = Canvas(self.root, width=self.image.width, height=self.image.height)
        self.canvas.pack()
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_image)
        
        self.user_location = None

    def load_ap_data(self, path):
        if os.path.exists(path):
            with open(path, "r") as file:
                return json.load(file)
        return []

    def scan_wifi(self):
        wifi = PyWiFi()
        iface = wifi.interfaces()[0]
        iface.scan()
        time.sleep(3)
        scan_results = iface.scan_results()
        
        ap_list = []
        for ap in scan_results:
            ap_mac = ap.bssid.lower().replace(":", "")
            if ap.ssid.strip() == "eduroam":
                ap_list.append({
                    "mac": ap_mac,
                    "rssi": ap.signal
                })
        return ap_list

    def average_scans(self, num_scans=3):
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

    def estimate_location(self, scan_data):
        # Find all known APs in scan data with their RSSI values
        ap_positions = []
        weights = []
        
        for ap in scan_data:
            for known_ap in self.ap_data:
                known_mac = known_ap["id"].lower().replace(":", "")
                if ap["mac"] == known_mac:
                    # Convert RSSI to weight (stronger signals get higher weight)
                    weight = ap["rssi"] + 100  # Convert to positive scale (-100 → 0, -50 → 50)
                    if weight <= 0:
                        continue  # Skip very weak signals
                    
                    # Get AP position in image coordinates
                    ap_x = known_ap["x"] * self.image.width
                    ap_y = known_ap["y"] * self.image.height
                    
                    ap_positions.append((ap_x, ap_y))
                    weights.append(weight ** 2)  # Square to emphasize stronger signals
                    break

        if not ap_positions:
            return None

        # Calculate weighted average position
        total_weight = sum(weights)
        weighted_x = sum(x * w for (x, y), w in zip(ap_positions, weights)) / total_weight
        weighted_y = sum(y * w for (x, y), w in zip(ap_positions, weights)) / total_weight

        # Plot reference APs
        for (x, y), w in zip(ap_positions, weights):
            self.canvas.create_oval(
                x-5, y-5, x+5, y+5,
                fill="#ffdd00", outline="black"  # Yellow for reference APs
            )

        return weighted_x, weighted_y

    def plot_user_location(self, x, y):
        self.canvas.create_oval(
            x-10, y-10, x+10, y+10,
            fill="#0066ff", outline="white", width=2  # Blue for user position
        )
        self.root.mainloop()

    def run(self):
        averaged_scan_data = self.average_scans(num_scans=3)
        
        if not averaged_scan_data:
            print("No Wi-Fi scan results found.")
            return
        
        user_location = self.estimate_location(averaged_scan_data)
        
        if user_location:
            self.plot_user_location(*user_location)
        else:
            print("No matching APs found in scan data.")

if __name__ == "__main__":
    image_path = "plan.jpg"
    app = WiFiLocalization(image_path)
    app.run()