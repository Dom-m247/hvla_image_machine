import tkinter as tk
from tkinter import ttk, filedialog, messagebox


class SourceInputWindow:
    def __init__(self, master, app):
        self.master = master
        self.app = app
        #establish window properties (random af nums lol)
        master.title("Source Input")
        master.geometry("700x550")
        master.minsize(700, 550)
        
        # Main container for source input and info
        main_container = ttk.Frame(master)
        main_container.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Source Input Frame (left side)
        source_frame = ttk.LabelFrame(main_container, text="Source Input", padding=10)
        source_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))
        
        # Source name label and entry
        ttk.Label(source_frame, text="Enter source name:", font=("Arial", 20)).pack(anchor="w", pady=(0, 5))
        self.source_var = tk.StringVar()
        self.source_entry = ttk.Entry(source_frame, textvariable=self.source_var, width=30, font=("Arial", 10))
        self.source_entry.pack(anchor="w", pady=(0, 10))
        # Trace source_var to enable Get Observations button when text is entered
        self.source_var.trace("w", self.on_source_change)
        
        # Validate button
        self.validate_button = ttk.Button(
            source_frame, 
            text="Check Valid Source", 
            command=self.validate_source
        )
        self.validate_button.pack(anchor="w", pady=(0, 5))
        
        # Get Observations button
        self.get_obs_button = ttk.Button(
            source_frame,
            text="Get Observations",
            command=self.get_observations,
            state="disabled"
        )
      
        
        # Radio Band selection
        ttk.Label(source_frame, text="Select Radio Band:", font=("Arial", 20)).pack(anchor="w", pady=(0, 5))
        self.band_var = tk.StringVar(value="All-Bands")
        bands = ["All-Bands","L", "S", "C", "X", "Ku", "K", "Ka", "Q", "W"]
        self.band_menu = ttk.Combobox(
            source_frame, 
            textvariable=self.band_var, 
            values=bands,
            state="readonly",
            width=27
        )
        self.band_menu.pack(anchor="w", pady=(0, 10))
        self.get_obs_button.pack(anchor="w", pady=(0, 15))
        
        # File Selection Frame
        file_frame = ttk.LabelFrame(master, text="Or Select Existing Observation File", padding=10)
        
        # File path display
        ttk.Label(file_frame, text="Selected file:", font=("Arial", 20)).pack(anchor="w", pady=(0, 5))
        self.file_path_var = tk.StringVar(value="No file selected")
        self.file_path_label = ttk.Label(
            file_frame, 
            textvariable=self.file_path_var,
            foreground="gray",
            wraplength=400
        )
        self.file_path_label.pack(anchor="w", pady=(0, 10), fill="both", expand=True)
        
        # Browse button
        self.browse_button = ttk.Button(
            file_frame,
            text="Browse for Source File",
            command=self.browse_file
        )
        self.browse_button.pack(anchor="w", pady=(0, 10))
        
        
        file_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Source Info Frame (right side)
        info_frame = ttk.LabelFrame(main_container, text="Source Information", padding=10)
        info_frame.pack(side="right", fill="both", expand=True, padx=(5, 0))
        
        # Info display text widget
        self.info_text = tk.Text(info_frame, height=15, width=30, state="disabled", wrap="word")
        self.info_text.pack(fill="both", expand=True, pady=(0, 10))
        
        # Clear info button
        #self.clear_info_button = ttk.Button(
        #    info_frame,
        #    text="Clear",
        #    command=self.clear_info
        #)
        #self.clear_info_button.pack(anchor="e")
        
        # Navigation buttons
        button_frame = ttk.Frame(master)
        button_frame.pack(fill="x", padx=10, pady=10)
        
        ttk.Button(
            button_frame,
            text="Next: Breakpoints",
            command=self.proceed_to_breakpoints
        ).pack(side="right", padx=5)
        
        ttk.Button(
            button_frame,
            text="Cancel",
            command=master.quit
        ).pack(side="right")
        
        self.selected_file = None
        self.source_validated = False
    
    def on_source_change(self, *args):
        """Disable Get Observations button when source text changes"""
        self.source_validated = False
        self.get_obs_button.config(state="disabled")
    
    def validate_source(self):
        """Placeholder for source validation"""
        source = self.source_var.get()
        if not source.strip():
            messagebox.showwarning("Input Error", "Please enter a source name")
            return
        # Validation logic goes here
        messagebox.showinfo("Validation", f"Source '{source}' validation logic here")
        
        # Mark source as validated and enable Get Observations button
        self.source_validated = True
        self.get_obs_button.config(state="normal")
        
        # Display source info
        self.display_source_info(source)

    
    def get_observations(self):
        """Get observations for the selected source"""
        source = self.source_var.get()
        messagebox.showinfo("Get Observations", f"Fetching observations for source: {source}")
    
    def display_source_info(self, source):
        """Display validated source information"""
        info_content = f"""Source Information:\n\nName: {source}\n\nStatus: Validated ✓
        \nBand: {self.band_var.get()}\n\nLast Updated: N/A\n\nObservations: N/A\n\nCoordinates: N/A"""
        self.info_text.config(state="normal")
        self.info_text.delete("1.0", "end")
        self.info_text.insert("1.0", info_content)
        self.info_text.config(state="disabled")
    
    def browse_file(self):
        """Open file dialog to select a source file"""
        file_path = filedialog.askopenfilename(
            title="Select Source File",
            filetypes=[("All Files", "*.*"), ("Text Files", "*.txt"), ("Data Files", "*.dat")]
        )
        if file_path:
            # Check if file has correct extension
            if file_path.endswith(('.ms', '.exp')):
                self.selected_file = file_path
                self.file_path_var.set(file_path)
            else:
                messagebox.showerror("Invalid File Type", "Please select a file ending in .ms or .exp")
                self.file_path_var.set("No file selected")
    
    def use_file(self):
        """Use the selected file as source"""
        if self.selected_file:
            if self.selected_file.endswith(('.ms', '.exp')):
                messagebox.showinfo("File Selected", f"Using file:\n{self.selected_file}")
            else:
                messagebox.showerror("Invalid File Type", "Selected file must end in .ms or .exp")
    
    def proceed_to_breakpoints(self):
        """Move to the breakpoints window"""
        source = self.source_var.get()
        band = self.band_var.get()
        
        if not source.strip() and not self.selected_file:
            messagebox.showwarning("Input Required", "Please enter a source or select a file")
            return
        
        # Store the data for the next window
        self.app.source_data = {
            "source": source,
            "band": band,
            "file": self.selected_file
        }
        
        # Close this window and open breakpoints window
        self.master.destroy()
        self.app.create_breakpoints_window()


class BreakpointsWindow:
    def __init__(self, master, app):
        self.master = master
        self.app = app
        master.title("Breakpoints Selection")
        master.geometry("650x550")
        master.minsize(650, 550)
        
        ttk.Label(
            master, 
            text="Select Processing Breakpoints",
            font=("Arial", 24, "bold")
        ).pack(pady=15)
        
        # Breakpoints frame
        breakpoints_frame = ttk.LabelFrame(master, text="Processing Stages", padding=15)
        breakpoints_frame.pack(fill="both", expand=True, padx=15, pady=10)
        
        # Checkboxes for breakpoints (allow multiple selections)
        self.breakpoint_vars = {
            "manual_flagging": tk.BooleanVar(value=False),
            "calibration": tk.BooleanVar(value=False),
            "image_generation": tk.BooleanVar(value=False)
        }
        
        breakpoints = [
            ("Manual Data Flagging", "manual_flagging"),
            ("Calibration", "calibration"),
            ("Image Generation", "image_generation")
        ]
        
        self.checkbuttons = []
        for text, value in breakpoints:
            cb = ttk.Checkbutton(
                breakpoints_frame,
                text=text,
                variable=self.breakpoint_vars[value]
            )
            cb.pack(anchor="w", pady=8)
            self.checkbuttons.append(cb)
        
        
        # Navigation buttons
        button_frame = ttk.Frame(master)
        button_frame.pack(fill="x", padx=15, pady=10)
        
        ttk.Button(
            button_frame,
            text="Back",
            command=self.go_back
        ).pack(side="left", padx=5)
        
        ttk.Button(
            button_frame,
            text="Submit",
            command=self.submit
        ).pack(side="right", padx=5)
        
        ttk.Button(
            button_frame,
            text="Cancel",
            command=master.quit
        ).pack(side="right")
    
    def go_back(self):
        """Return to the source input window"""
        self.master.destroy()
        self.app.create_source_window()
    
    def submit(self):
        """Submit the selected breakpoints"""
        selected_breakpoints = [name for name, var in self.breakpoint_vars.items() if var.get()]
        source_info = self.app.source_data
        
        if not selected_breakpoints:
            messagebox.showwarning("No Selection", "Please select at least one breakpoint")
            return
        
        # Format breakpoint names for display
        breakpoint_names = {
            "manual_flagging": "Manual Data Flagging",
            "calibration": "Calibration",
            "image_generation": "Image Generation"
        }
        breakpoint_display = ", ".join([breakpoint_names[bp] for bp in selected_breakpoints])
        
        # Create summary dictionary
        summary_dict = {
            "archive_file": source_info['source'] or source_info['file'],
            "band": source_info['band'],
            "breakpoints": selected_breakpoints
        }
        # Store in app
        self.app.summary_dict = summary_dict
        self.master.quit()
        self.master.destroy()



class HVLAApp:
    def __init__(self):
        self.root = None
        self.source_data = {}
        self.summary_dict = None
        self.create_source_window()
    
    def create_source_window(self):
        """Create the source input window"""
        self.root = tk.Tk()
        self.source_window = SourceInputWindow(self.root, self)
        self.root.mainloop()
    
    def create_breakpoints_window(self):
        """Create the breakpoints selection window"""
        self.root = tk.Tk()
        self.breakpoints_window = BreakpointsWindow(self.root, self)
        self.root.mainloop()

def run_hvla_app():
    app = HVLAApp()
    return app.summary_dict
