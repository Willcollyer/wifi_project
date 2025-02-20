import tkinter as tk
from tkinter import simpledialog
from PIL import Image, ImageTk
import json
import os

class FloorPlanMarker:
    def __init__(self, image_path):
        self.root = tk.Tk()
        self.root.title("AP Location Marker")

        # Load floor plan image
        self.image = Image.open(image_path)
        self.tk_image = ImageTk.PhotoImage(self.image)

        # Create canvas
        self.canvas = tk.Canvas(self.root,
                              width=self.image.width,
                              height=self.image.height)
        self.canvas.pack()
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_image)

        # Initialize variables
        self.ap_locations = self.load_from_json()
        self.current_markers = []

        # Draw existing markers
        for ap in self.ap_locations:
            self.draw_marker(ap["x"], ap["y"])

        # Bind click event
        self.canvas.bind("<Button-1>", self.mark_location)

        # Add save button
        save_btn = tk.Button(self.root, text="Save to JSON", command=self.save_to_json)
        save_btn.pack(pady=10)

    def mark_location(self, event):
        # Get click coordinates relative to image
        x = event.x / self.image.width
        y = event.y / self.image.height

        # Get AP identifier from user
        ap_id = simpledialog.askstring("AP Identifier", "Enter AP identifier (e.g., AP-01):")

        if ap_id:
            # Store normalized coordinates (0-1 range)
            self.ap_locations.append({
                "id": ap_id,
                "x": round(x, 4),
                "y": round(y, 4)
            })

            # Visual marker (scaled to image size)
            marker_size = 10
            self.current_markers.append(self.canvas.create_oval(
                event.x - marker_size, event.y - marker_size,
                event.x + marker_size, event.y + marker_size,
                fill='red', outline='white'
            ))

    def save_to_json(self):
        with open("ap_locations.json", "w") as f:
            json.dump(self.ap_locations, f, indent=2)
        print("AP locations saved to ap_locations.json")

    def load_from_json(self):
        if os.path.exists("ap_locations.json"):
            with open("ap_locations.json", "r") as f:
                return json.load(f)
        return []

    def draw_marker(self, x, y):
        marker_size = 10
        self.canvas.create_oval(
            x * self.image.width - marker_size, y * self.image.height - marker_size,
            x * self.image.width + marker_size, y * self.image.height + marker_size,
            fill='red', outline='white'
        )

    def run(self):
        self.root.mainloop()

# Usage
if __name__ == "__main__":
    image_path = "plan.jpg"  # Change to your image path
    app = FloorPlanMarker(image_path)
    app.run()
