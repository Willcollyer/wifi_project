import time
import math
from pywifi import PyWiFi, const

# Constants for distance estimation
REFERENCE_SIGNAL_STRENGTH = -30  # dBm (signal strength at 1 meter)
PATH_LOSS_EXPONENT = 3.0  # Typical value for indoor environments

def get_wifi_info():
    wifi = PyWiFi()
    iface = wifi.interfaces()[0]  # Use the first available interface

    iface.scan()  # Start scanning
    time.sleep(2)  # Wait for scan results

    scan_results = iface.scan_results()  # Get scan results
    networks = []

    for network in scan_results:
        ssid = network.ssid  # Access the SSID
        mac = network.bssid  # Access the MAC address
        signal_strength = network.signal  # Access the signal strength

        # Only add networks with the SSID "eduroam"
        if ssid.lower() == "eduroam":
            networks.append({
                'ssid': ssid,
                'mac': mac,
                'signal_strength': signal_strength
            })

    return networks

def calculate_distance(signal_strength):
    """
    Estimate the distance to the AP based on signal strength (in dBm).
    Formula: Distance = 10^((A - L) / (10 * n))
    where:
    A = reference signal strength at 1 meter (typically -30 dBm)
    L = measured signal strength (in dBm)
    n = path loss exponent (typically 3)
    """
    distance = 10 ** ((REFERENCE_SIGNAL_STRENGTH - signal_strength) / (10 * PATH_LOSS_EXPONENT))
    return distance

def display_wifi_info():
    while True:
        networks = get_wifi_info()

        # Sort networks based on signal strength in descending order
        networks = sorted(networks, key=lambda x: x["signal_strength"], reverse=True)

        # Display information for the networks
        if networks:
            print("\nEduroam Networks:")
            for i, network in enumerate(networks):
                distance = calculate_distance(network["signal_strength"])
                print(f"{i + 1}. SSID: {network['ssid']}, MAC: {network['mac']}, Signal Strength: {network['signal_strength']} dBm, Estimated Distance: {distance:.2f} meters")
        else:
            print("\nNo eduroam networks found.")

        time.sleep(5)  # Update every 5 seconds

if __name__ == "__main__":
    display_wifi_info()
