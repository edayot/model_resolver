import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox
import json

class PixelGrid:
    def __init__(self, master):
        self.master = master
        self.master.title("3D Pixel Grid Editor")
        self.grid_size = 16
        self.current_layer = 0
        self.pixels = [[[{"active": False, "color": "#000000"} for _ in range(self.grid_size)] for _ in range(self.grid_size)] for _ in range(self.grid_size)]
        self.create_widgets()

    def create_widgets(self):
        self.canvas = tk.Canvas(self.master, width=800, height=800, bg="white")
        self.canvas.pack(side=tk.LEFT)
        self.canvas.bind("<Button-1>", self.on_canvas_click)

        self.control_frame = tk.Frame(self.master)
        self.control_frame.pack(side=tk.RIGHT, fill=tk.Y)

        self.save_button = tk.Button(self.control_frame, text="Save", command=self.save_grid)
        self.save_button.pack(pady=10)

        self.load_button = tk.Button(self.control_frame, text="Load", command=self.load_grid)
        self.load_button.pack(pady=10)

        self.generate_button = tk.Button(self.control_frame, text="Generate Command", command=self.generate_command)
        self.generate_button.pack(pady=10)

        self.color_button = tk.Button(self.control_frame, text="Choose Color", command=self.choose_color)
        self.color_button.pack(pady=10)

        self.layer_label = tk.Label(self.control_frame, text=f"Layer: {self.current_layer}")
        self.layer_label.pack(pady=10)

        self.prev_layer_button = tk.Button(self.control_frame, text="Previous Layer", command=self.prev_layer)
        self.prev_layer_button.pack(pady=10)

        self.next_layer_button = tk.Button(self.control_frame, text="Next Layer", command=self.next_layer)
        self.next_layer_button.pack(pady=10)

        self.current_color = "#000000"
        self.draw_grid()

    def draw_grid(self):
        self.canvas.delete("all")
        cell_size = 800 // self.grid_size
        for x in range(self.grid_size):
            for y in range(self.grid_size):
                if self.pixels[x][y][self.current_layer]["active"]:
                    color = self.pixels[x][y][self.current_layer]["color"]
                else:
                    color = "#FFFFFF"
                self.canvas.create_rectangle(
                    x * cell_size, y * cell_size, (x + 1) * cell_size, (y + 1) * cell_size,
                    fill=color, outline="black"
                )

    def on_canvas_click(self, event):
        cell_size = 800 // self.grid_size
        x = event.x // cell_size
        y = event.y // cell_size
        z = self.current_layer
        if 0 <= x < self.grid_size and 0 <= y < self.grid_size:
            self.pixels[x][y][z]["active"] = not self.pixels[x][y][z]["active"]
            self.pixels[x][y][z]["color"] = self.current_color if self.pixels[x][y][z]["active"] else "#000000"
            self.draw_grid()

    def choose_color(self):
        color_code = colorchooser.askcolor(title="Choose color")
        if color_code:
            self.current_color = color_code[1]

    def save_grid(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json")])
        if file_path:
            with open(file_path, 'w') as f:
                json.dump(self.pixels, f)
            messagebox.showinfo("Save", "Grid saved successfully!")

    def load_grid(self):
        file_path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
        if file_path:
            with open(file_path, 'r') as f:
                self.pixels = json.load(f)
            self.draw_grid()
            messagebox.showinfo("Load", "Grid loaded successfully!")

    def generate_command(self):
        flags = []
        colors = []
        for x in range(self.grid_size):
            for y in range(self.grid_size):
                for z in range(self.grid_size):
                    if self.pixels[x][y][z]["active"]:
                        flags.append(1)
                        color = self.pixels[x][y][z]["color"]
                        if color is None:
                            color = "#000000"
                        colors.append(int(color.lstrip('#'), 16))
                    else:
                        flags.append(0)
                        colors.append(0)
        command = f'/item replace entity @e[type=minecraft:item_display,limit=1] contents with diamond[minecraft:item_model="custom_item:test",minecraft:custom_model_data={{flags:{flags},colors:{colors}}}]'

        # Create a new window to display the command
        command_window = tk.Toplevel(self.master)
        command_window.title("Generated Command")
        
        # Create a text widget to display the command
        text_widget = tk.Text(command_window, wrap=tk.WORD)
        text_widget.insert(tk.END, command)
        text_widget.pack(expand=True, fill=tk.BOTH)
        
        # Add a button to close the window
        close_button = tk.Button(command_window, text="Close", command=command_window.destroy)
        close_button.pack(pady=10)


    def prev_layer(self):
        if self.current_layer > 0:
            self.current_layer -= 1
            self.layer_label.config(text=f"Layer: {self.current_layer}")
            self.draw_grid()

    def next_layer(self):
        if self.current_layer < self.grid_size - 1:
            self.current_layer += 1
            self.layer_label.config(text=f"Layer: {self.current_layer}")
            self.draw_grid()

if __name__ == "__main__":
    root = tk.Tk()
    app = PixelGrid(root)
    root.mainloop()