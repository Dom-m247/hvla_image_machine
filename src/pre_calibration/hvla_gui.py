import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from classes.constants import *

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
        self.band_var = tk.StringVar(value="auto")
        bands = ["auto","L", "S", "C", "X", "Ku", "K", "Ka", "Q", "W"]
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
        self.browse_archive_button = ttk.Button(
            file_frame,
            text="Browse for archive File",
            command=self.browse_archive_file
        )
        self.browse_archive_button.pack(anchor="w", pady=(0, 10))

        self.browse_ms_button = ttk.Button(
            file_frame,
            text="Browse for measrument set",
            command=self.browse_ms_file
        )
        self.browse_ms_button.pack(anchor="w", pady=(0, 10))
        
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
        #send to other part, return with archive file download destination
        #self.selected_file = dowloadArchive()
        
    
    def display_source_info(self, source):
        """Display validated source information"""
        info_content = f"""Source Information:\n\nName: {source}\n\nStatus: Validated ✓
        \nBand: {self.band_var.get()}\n\nLast Updated: N/A\n\nObservations: N/A\n\nCoordinates: N/A"""
        self.info_text.config(state="normal")
        self.info_text.delete("1.0", "end")
        self.info_text.insert("1.0", info_content)
        self.info_text.config(state="disabled")
    
    def browse_archive_file(self):
        """Open file dialog to select a source file"""
        file_path = filedialog.askopenfilename(
            title="Select Archive File",
            filetypes=[("All Files", "*.*"), ("Text Files", "*.txt"), ("Data Files", "*.dat"),("exp Files", "*.exp")]
        )
        if file_path:
            # Check if file has correct extension
            if file_path.endswith(('.ms', '.exp')):
                self.selected_file = file_path
                self.file_path_var.set(file_path)
            else:
                messagebox.showerror("Invalid File Type", "Please select a file ending in .ms or .exp")
                self.file_path_var.set("No file selected")

    def browse_ms_file(self):
        """Open file dialog to select a source file"""
        file_path = filedialog.askdirectory(
            title="Select measurment Set directory"
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
        if source == "":
            source = None
        
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
        master.geometry("680x750")
        master.minsize(680, 750)
        
        ttk.Label(
            master, 
            text="Select Processing Options",
            font=("Arial", 24, "bold")
        ).pack(pady=15)
        
        # Breakpoints frame
        breakpoints_frame = ttk.LabelFrame(master, text="Processing Stages", padding=15)
        breakpoints_frame.pack(fill="both", expand=True, padx=15, pady=10)
        
        # Options container (calibration and image generation side by side)
        options_container = ttk.Frame(master)
        options_container.pack(fill="both", expand=True, padx=15, pady=10)
        
        # Calibration Options Frame
        calibration_frame = ttk.LabelFrame(options_container, text="Calibration Options", padding=15)
        calibration_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))
        
        # Solution Interval (solint) dropdown
        ttk.Label(calibration_frame, text="Solution Interval (solint):", font=("Arial", 10)).pack(anchor="w", pady=(0, 5))
        self.solint_var = tk.StringVar(value="int")
        solint_options = ["int", "inf", "120s", "60s", "30s"]
        self.solint_menu = ttk.Combobox(
            calibration_frame,
            textvariable=self.solint_var,
            values=solint_options,
            state="readonly",
            width=30
        )
        self.solint_menu.pack(anchor="w", pady=(0, 15))
        
        #PLACEHOLDER
        # Additional calibration options #PLACEHOLDER
        ttk.Label(calibration_frame, text="Pick Calibration Method", font=("Arial", 10)).pack(anchor="w", pady=(0, 5))
        self.amp_cal_mode = tk.StringVar(value="auto")
        amp_cal_options = ["auto","gain", "phase", "gain/phase", "None"]
        self.calib_model_menu = ttk.Combobox(
            calibration_frame,
            textvariable=self.amp_cal_mode,
            values=amp_cal_options,
            state="readonly",
            width=30
        )
        self.calib_model_menu.pack(anchor="w", pady=(0, 15))
        
        ttk.Label(calibration_frame, text="Reference Antenna:", font=("Arial", 10)).pack(anchor="w", pady=(0, 5))
        self.ref_antenna_var = tk.StringVar(value="auto")
        ref_antenna_options = ["Default","auto", "EA01", "EA02", "EA03"]
        self.ref_antenna_menu = ttk.Combobox(
            calibration_frame,
            textvariable=self.ref_antenna_var,
            values=ref_antenna_options,
            state="readonly",
            width=30
        )
        self.ref_antenna_menu.pack(anchor="w", pady=(0, 15))
        
        ttk.Label(calibration_frame, text="Minimum SNR Ratio:", font=("Arial", 10)).pack(anchor="w", pady=(0, 5))
        self.snr_var = tk.DoubleVar(value=MIN_SNR)
        self.snr_spinbox = ttk.Spinbox(
            calibration_frame,
            from_=0,
            to=10,
            textvariable=self.snr_var,
            width=30
        )
        self.snr_spinbox.pack(anchor="w", pady=(0, 15))
        #PLACEHOLDER
        
        # Image Generation Options Frame
        image_frame = ttk.LabelFrame(options_container, text="Image Generation Options", padding=15)
        image_frame.pack(side="right", fill="both", expand=True, padx=(5, 0))

        self.use_custom_naming_var = tk.BooleanVar(value=False)
        self.use_custom_image_name_check = ttk.Checkbutton(
            image_frame,
            text="Set a custom filename for image",
            variable=self.use_custom_naming_var,
            command=self.toggle_image_name_entry
        )
        self.use_custom_image_name_check.pack(anchor="w", pady=(0, 5))

        # Image filename
        ttk.Label(image_frame, text="Image Filename(ExampleName_XX):", font=("Arial", 10)).pack(anchor="w", pady=(0, 5))
        self.image_filename_var = tk.StringVar(value="image_name")
        self.image_filename_entry = ttk.Entry(
            image_frame,
            textvariable=self.image_filename_var,
            width=30,
            state='disabled'
        )
        self.image_filename_entry.pack(anchor="w", pady=(0, 5))
        
        
        # Image size
        ttk.Label(image_frame, text="Image Size (pixels):", font=("Arial", 10)).pack(anchor="w", pady=(0, 5))
        self.image_size_var = tk.IntVar(value=DEFAULT_IMAGE_SIZE[1]) #1 pulls the first of the [#,#] square 
        self.image_size_spinbox = ttk.Spinbox(
            image_frame,
            from_=256,
            to=4096,
            textvariable=self.image_size_var,
            width=30
        )
        self.image_size_spinbox.pack(anchor="w", pady=(0, 5))
        
        # Interactive mode
        ttk.Label(image_frame, text="Interactive Mode:", font=("Arial", 10)).pack(anchor="w", pady=(0, 5))
        self.interactive_var = tk.BooleanVar(value=False)
        self.interactive_check = ttk.Checkbutton(
            image_frame,
            text="set interactive cleaning",
            variable=self.interactive_var
        )
        self.interactive_check.pack(anchor="w", pady=(0, 5))

        ttk.Label(image_frame, text="Deconvolver", font=("Arial", 10)).pack(anchor="w", pady=(0, 5))
        self.deconvolver = tk.StringVar(value="mtmfs")
        self.deconvolver_options = ["mtmfs","hogbom", "clark", "multisclae","mem","clarkstokes","asp"]
        self.deconvolver_choice = ttk.Combobox(
            image_frame,
            textvariable=self.deconvolver,
            values=self.deconvolver_options,
            state="readonly",
            width=30
        )
        self.deconvolver_choice.pack(anchor="w", pady=(0, 5))

        ttk.Label(image_frame, text="weighting", font=("Arial", 10)).pack(anchor="w", pady=(0, 5))
        self.weighting = tk.StringVar(value="briggs")
        weighting_choice = ["briggs","natural", "uniform", "superuniform","radial","briggs","briggsabs","briggsbwtaper"]
        self.weighting_choice_menu = ttk.Combobox(
            image_frame,
            textvariable=self.weighting,
            values=weighting_choice,
            state="readonly",
            width=30
        )
        self.weighting_choice_menu.pack(anchor="w", pady=(0, 15))
        
        
        # Cell size with manual override
        ttk.Label(image_frame, text="Cell Size Override:", font=("Arial", 10)).pack(anchor="w", pady=(0, 5))
        self.use_custom_cell_var = tk.BooleanVar(value=False)
        self.use_custom_cell_check = ttk.Checkbutton(
            image_frame,
            text="Set a cell size(default=1/10 Band resolution)",
            variable=self.use_custom_cell_var,
            command=self.toggle_cell_size_entry
        )
        self.use_custom_cell_check.pack(anchor="w", pady=(0, 5))
        
        self.cell_size_var = tk.DoubleVar(value=0.0)
        self.cell_size_entry = ttk.Entry(
            image_frame,
            textvariable=self.cell_size_var,
            width=30,
            state="disabled"
        )
        self.cell_size_entry.pack(anchor="w", pady=(0, 5))

        # Do self_calibration cycles 
        #ttk.Label(image_frame, text="", font=("Arial", 10)).pack(anchor="w", pady=(0, 5))
        self.do_self_cal_var = tk.BooleanVar(value=False)
        self.do_self_cal_check = ttk.Checkbutton(
            image_frame,
            variable=self.do_self_cal_var,
            text='Do self_cal Cycles',
            command=self.toggle_self_cal_entry
        )
        self.do_self_cal_check.pack(anchor="w", pady=(0, 5))
        
        #self.cell_size_var = tk.DoubleVar(value=0.0)
        ttk.Label(image_frame, text="Self Calibration Cycles:", font=("Arial", 10)).pack(anchor="w", pady=(0, 5))
        self.self_cal_cycle_var = tk.IntVar(value=1)
        self.self_cal_cycle_spinbox = ttk.Spinbox(
            image_frame,
            from_=0,
            to=4096,
            textvariable=self.self_cal_cycle_var,
            width=10,
            state='disabled'
        )
        self.self_cal_cycle_spinbox.pack(anchor="w", pady=(0, 5))

        # Checkboxes for breakpoints (allow multiple selections)
        self.breakpoint_vars = {}
        breakpoints = []
        for key in BREAKPOINTS.keys():
            self.breakpoint_vars.update({f"{key}" : tk.BooleanVar(value=False)})
            breakpoints.append((BREAKPOINTS[key], key))
            
        #self.breakpoint_vars = {
        #    "manual_flagging": tk.BooleanVar(value=False),
        #    "calibration": tk.BooleanVar(value=False),
        #    "manual_clean": tk.BooleanVar(value=False),
        #    "display_image":tk.BooleanVar(value=False)
        #    
        #}
        #
        #breakpoints = [
        #    ("Manual Data Flagging", "manual_flagging"),
        #    ("Calibration", "calibration"),
        #    ("Manual self-cal(launches casa)", "manual_clean"),
        #    ("Display Image After Generation","display_image" )
        #]
        
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
        self.app.create_source_window() #add options, to autopop?
    
    def toggle_cell_size_entry(self):
        """Enable/disable cell size entry based on checkbox state"""
        if self.use_custom_cell_var.get():
            self.cell_size_entry.config(state="normal")
        else:
            self.cell_size_entry.config(state="disabled")

    def toggle_image_name_entry(self):
        """Enable/disable custom file nameing based on checkbox state"""
        if self.use_custom_naming_var.get():
            self.image_filename_entry.config(state="normal")
        else:
            self.image_filename_entry.config(state="disabled")

    def toggle_self_cal_entry(self):
        """Enable/disable custom file nameing based on checkbox state"""
        if self.do_self_cal_var.get():
            self.self_cal_cycle_spinbox.config(state="normal")
        else:
            self.self_cal_cycle_spinbox.config(state="disabled")
    
    def submit(self):
        """Submit the selected breakpoints"""
        selected_breakpoints = [name for name, var in self.breakpoint_vars.items() if var.get()]
        source_info = self.app.source_data
        
        # Format breakpoint names for display
        #breakpoint_names = {
        #    "manual_flagging": "Manual Data Flagging",
        #    "calibration": "Calibration",
        #    "manual_clean": "Manual Clean",
        #    "display_image":"Display Image After"
        #}
        breakpoint_display = ", ".join([BREAKPOINTS[bp] for bp in selected_breakpoints])
        
        # Create summary dictionary
        summary_dict = {
            "source": source_info['source'],
            "archive_file": source_info['file'],
            "band": source_info['band'],
            "breakpoints": selected_breakpoints,
            "solint": self.solint_var.get(),
            "custom_amp_cal": self.amp_cal_mode.get(),
            "reference_antenna": self.ref_antenna_var.get(),
            "min_snr": self.snr_var.get(),
            "image_filename": self.image_filename_var.get() if self.use_custom_naming_var.get() else None,
            "image_size": [self.image_size_var.get(),self.image_size_var.get()],
            "interactive_image": self.interactive_var.get(),
            "use_custom_cell_size": self.use_custom_cell_var.get(),
            "cell_size": self.cell_size_var.get() if self.use_custom_cell_var.get() else None,
            "deconvolver":self.deconvolver.get(),
            "weighting":self.weighting.get(),
            "do_self_cal":self.do_self_cal_var.get(),
            "self_cal_cycles":self.self_cal_cycle_var.get() if self.do_self_cal_var.get() else None,
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
