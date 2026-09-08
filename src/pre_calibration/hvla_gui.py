from pprint import pp
from pathlib import Path
from types import SimpleNamespace
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from classes.constants import *
from classes import creds
from API_integrations import NED

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
        self.get_obs_button.pack(anchor="w", pady=(0, 2))

        #say why the button is unavailable rather than leaving it mysteriously greyed
        self.get_obs_status_var = tk.StringVar()
        ttk.Label(
            source_frame,
            textvariable=self.get_obs_status_var,
            foreground="gray",
            wraplength=260
        ).pack(anchor="w", pady=(0, 15))
        
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
            text="Browse for archive File(s)",
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
        self.selected_files = []   #every file of a multi-file segment; [] when one was picked
        self.source_validated = False
        #set later by validate_source; init here so proceed_to_breakpoints never AttributeErrors
        self.source_ra = ''
        self.source_decl = ''
        self.search_alias = ''
        self.redshift = ''
        #the archive search needs credentials; checked once at startup, since the
        #file is not going to appear while the window is open
        self.creds_available = self._creds_available()
        self.proj_code = ''
        self._refresh_get_obs_state()

    @staticmethod
    def _creds_available():
        """True when the credentials file the archive search needs is present."""
        try:
            creds.path()
            return True
        except FileNotFoundError:
            return False

    def _refresh_get_obs_state(self):
        """Enable Get Observations only when it could actually do something.

        Two gates: credentials for the remote search, and a validated source to
        search for -- the query goes out under the NED-resolved alias, not the
        raw typed text, so validation has to happen first.
        """
        if not self.creds_available:
            self.get_obs_button.config(state="disabled")
            self.get_obs_status_var.set("Archive search unavailable: no credentials file found.")
        elif not self.source_validated:
            self.get_obs_button.config(state="disabled")
            self.get_obs_status_var.set("Check the source name to enable the archive search.")
        else:
            self.get_obs_button.config(state="normal")
            self.get_obs_status_var.set("")

    def _set_busy(self, busy, message=""):
        """Lock the search controls while a remote call is in flight."""
        if busy:
            self.get_obs_button.config(state="disabled")
            self.validate_button.config(state="disabled")
            self.get_obs_status_var.set(message)
        else:
            self.validate_button.config(state="normal")
            self._refresh_get_obs_state()

    def _run_async(self, work, done):
        """Run `work` off the main thread, delivering its result to `done` on it.

        Tk is not thread-safe, so the worker touches no widget: it hands
        (result, error) back through master.after(). Without this the window
        would freeze for the length of every remote call.
        """
        def runner():
            try:
                result, error = work(), None
            except Exception as exc:
                result, error = None, exc
            self.master.after(0, lambda: done(result, error))
        threading.Thread(target=runner, daemon=True).start()

    def on_source_change(self, *args):
        """Re-gate Get Observations when the source text changes"""
        self.source_validated = False
        self._refresh_get_obs_state()
    
    def validate_source(self):
        """Placeholder for source validation"""
        source = self.source_var.get()
        if not source.strip():
            messagebox.showwarning("Input Error", f" {source.strip()}, Please enter a source name")
            return
        # Validation logic goes here
        #messagebox.showinfo("Validation", f"Source '{source}' validation logic here")
        #results = NED.NED_API.obj_exists(source)
        messagebox.showinfo("source Validation","this may take a moment")
        try:
            results = NED.NED_API.obj_exists(source)
            if results is False:
                messagebox.showwarning("validation error", "Please check your identifier and try again")
                return
        except Exception as e:
            messagebox.showerror("Error", f"{e}")
            return
        # Mark source as validated and enable Get Observations button
        
        self.source_validated = True
        self.source_ra = results['ra_decl']['ra']
        self.source_decl = results['ra_decl']['decl']
        self.search_alias = results['alias']
        self.redshift = results.get('redshift', '')
        self._refresh_get_obs_state()

        # Display source info
        self.display_source_info(source)


    def get_observations(self):
        """Search the archive for the validated source and offer the results."""
        band = self.band_var.get()
        options = SimpleNamespace(search_alias=self.search_alias or self.source_var.get(),
                                  band=band)
        self._set_busy(True, "Searching the archive...")

        def work():
            #imported here so the window still opens on a machine without the
            #search dependencies installed -- only this button needs them
            from archive_dowload.radio_search_integration import RadioSearchIntegration
            with RadioSearchIntegration.connect() as rs:
                return RadioSearchIntegration.run_search(rs, options)

        self._run_async(work, self._on_search_done)

    def _on_search_done(self, observations, error):
        """Back on the main thread with the search result."""
        self._set_busy(False)
        if error is not None:
            messagebox.showerror("Archive Search Failed", str(error))
            return
        if not observations:
            band = self.band_var.get()
            in_band = "" if band in ("", "auto") else f" in band {band}"
            messagebox.showinfo(
                "No Observations",
                f"No observations found for '{self.search_alias}'{in_band}.\n\n"
                "A name that resolves can still have no archive data in the "
                "chosen band; try 'auto' or check the source name."
            )
            return
        ObservationResultsWindow(self.master, self, observations)

    def download_observation(self, observation):
        """Fetch the chosen observation's files and fill in the file selection."""
        target = SimpleNamespace(proj_code=observation.proj_code, archive_files=[])
        #carried through to Options so the run records which project it came from
        self.proj_code = observation.proj_code
        self._set_busy(True, f"Downloading {observation.proj_code}; "
                             f"the file selection will fill in automatically ...")

        def work():
            from archive_dowload.radio_search_integration import (
                DelosDownload, RadioSearchIntegration, parseArchFileInfo)
            #a second short-lived session rather than holding one open while the
            #user reads the results table
            with RadioSearchIntegration.connect() as rs:
                archfiles = parseArchFileInfo(rs('--archfileinfo', observation.proj_code))
            files = RadioSearchIntegration.select_segment_files(archfiles, observation)
            if not files:
                raise RuntimeError(
                    f"No archive files are listed for segment {observation.seg}.")
            DelosDownload(files, target).download()
            return target.archive_files

        self._run_async(work, self._on_download_done)

    def _on_download_done(self, paths, error):
        """Populate the file selection with whatever landed on disk."""
        self._set_busy(False)
        if error is not None:
            messagebox.showerror("Download Failed", str(error))
            return
        if not paths:
            messagebox.showwarning("Download", "The download returned no files.")
            return
        self.selected_files = list(paths) if len(paths) > 1 else []
        self.selected_file = paths[0]
        self.file_path_var.set(self._archive_summary(paths))
        messagebox.showinfo(
            "Download Complete",
            f"{len(paths)} file(s) downloaded. The file selection is filled in.")


    def display_source_info(self, source):
        """Display validated source information"""
        info_content = f"""Source Information:\n\nName: {source}\n\nStatus: Validated ✓
        \nBand: {self.band_var.get()}
        \nSearch Alias: {self.search_alias}
        \n\nLast Updated: N/A\n\nObservations: N/A\n\nCoordinates: N/A"""
        self.info_text.config(state="normal")
        self.info_text.delete("1.0", "end")
        self.info_text.insert("1.0", info_content)
        self.info_text.config(state="disabled")
    
    def browse_archive_file(self):
        """Open file dialog to select the archive file(s).

        A segment held locally is several raw archive files that importvla
        concatenates into one MS, so the dialog allows a multi-selection.
        """
        file_paths = filedialog.askopenfilenames(
            title="Select Archive File(s)",
            filetypes=[("All Files", "*.*"), ("Text Files", "*.txt"), ("Data Files", "*.dat"),("exp Files", "*.exp")]
        )
        if file_paths:
            # Check every file has correct extension
            invalid = [p for p in file_paths if not p.endswith(('.ms',) + ARCHIVE_SUFFIXES)]
            if invalid:
                messagebox.showerror("Invalid File Type", "Please select files ending in .ms or .exp")
                self.file_path_var.set("No file selected")
                return
            paths = list(file_paths)
            self.selected_files = paths if len(paths) > 1 else []
            self.selected_file = paths[0]
            self.file_path_var.set(self._archive_summary(paths))

    @staticmethod
    def _archive_summary(file_paths):
        """What the label shows for the selection: the path, or a file count + names."""
        if len(file_paths) == 1:
            return file_paths[0]
        names = ", ".join(Path(p).name for p in file_paths)
        return f"{len(file_paths)} files in {Path(file_paths[0]).parent}: {names}"

    def browse_ms_file(self):
        """Open file dialog to select a source file"""
        file_path = filedialog.askdirectory(
            title="Select measurment Set directory"
        )
        if file_path:
            # Check if file has correct extension
            if file_path.endswith(('.ms', '.exp')):
                self.selected_file = file_path
                self.selected_files = []   #an MS is imported data, never a multi-file segment
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
            "file": self.selected_file,
            "files": self.selected_files,
            "source_ra":self.source_ra,
            "source_decl":self.source_decl,
            "search_alias": self.search_alias,
            "redshift": self.redshift,
            "proj_code": self.proj_code,
        }
        # Close this window and open breakpoints window
        self.master.destroy()
        self.app.create_breakpoints_window()


class ObservationResultsWindow:
    """The archive search results, for the user to pick one observation from.

    'Okay' closes the window, downloads the chosen observation's files and fills
    in the parent window's file selection with what arrived.
    """

    #(attribute on nrao_observeration, heading, column width)
    COLUMNS = [
        ('date', 'Date', 95),
        ('proj_code', 'Project', 100),
        ('seg', 'Segment', 90),
        ('band', 'Band', 55),
        ('cfg', 'Config', 60),
        ('resln', 'Resolution', 90),
        ('las', 'LAS', 80),
        ('sensitivity', 'Sensitivity', 95),
        ('separation', 'Separation', 90),
        ('time', 'Time', 70),
        ('name', 'Name', 130),
    ]

    def __init__(self, parent, source_window, observations):
        self.source_window = source_window
        self.observations = observations

        self.window = tk.Toplevel(parent)
        self.window.title("Archive Search Results")
        self.window.geometry("1000x420")
        self.window.minsize(700, 300)
        #modal: the parent's source/band drive this list, so editing them behind
        #it would leave the table describing a search that no longer applies
        self.window.transient(parent)
        self.window.grab_set()

        ttk.Label(
            self.window,
            text=f"{len(observations)} observation(s) found. Select one to download:",
            font=("Arial", 11)
        ).pack(anchor="w", padx=10, pady=(10, 5))

        table_frame = ttk.Frame(self.window)
        table_frame.pack(fill="both", expand=True, padx=10)

        self.tree = ttk.Treeview(
            table_frame,
            columns=[key for key, _, _ in self.COLUMNS],
            show="headings",
            selectmode="browse"
        )
        for key, heading, width in self.COLUMNS:
            self.tree.heading(key, text=heading)
            self.tree.column(key, width=width, anchor="w", stretch=False)

        scroll_y = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        scroll_x = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x.grid(row=1, column=0, sticky="ew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        #the row index is the iid, so a selection maps straight back to its object
        for index, obs in enumerate(observations):
            values = [str(getattr(obs, key, '') or '') for key, _, _ in self.COLUMNS]
            self.tree.insert("", "end", iid=str(index), values=values)
        self.tree.bind("<Double-1>", lambda event: self.okay())

        button_frame = ttk.Frame(self.window)
        button_frame.pack(fill="x", padx=10, pady=10)
        #disabled until a row is picked, so Okay never has to warn about an empty
        #selection -- the same shape as the Get Observations button
        self.okay_button = ttk.Button(button_frame, text="Okay", command=self.okay,
                                      state="disabled")
        self.okay_button.pack(side="right", padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side="right")
        self.tree.bind('<<TreeviewSelect>>', lambda _e: self.okay_button.config(
            state="normal" if self.tree.selection() else "disabled"))

    def selected_observation(self):
        """The observation the user highlighted, or None."""
        selection = self.tree.selection()
        if not selection:
            return None
        return self.observations[int(selection[0])]

    def okay(self):
        """Close, then download the selection through the parent window."""
        observation = self.selected_observation()
        if observation is None:
            return   #the button is disabled without a selection
        self.cancel()
        self.source_window.download_observation(observation)

    def cancel(self):
        """Close without downloading."""
        self.window.grab_release()
        self.window.destroy()


class BreakpointsWindow:
    def __init__(self, master, app):
        self.master = master
        self.app = app
        master.title("Processing Options")
        master.geometry("680x750")
        master.minsize(680, 750)
        
        ttk.Label(
            master, 
            text="Select Processing Options",
            font=("Arial", 24, "bold")
        ).pack(pady=15)
        
        # Options container (calibration and image generation side by side)
        options_container = ttk.Frame(master)
        options_container.pack(fill="both", expand=True, padx=15, pady=10)

        # Calibration Options Frame
        calibration_frame = ttk.LabelFrame(options_container, text="Calibration Options", padding=15)
        calibration_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))

        #decision-point dropdowns, rendered from the DECISIONS registry into the frame
        #each one names in 'gui'. Adding a decision point adds a dropdown here.
        self.decision_vars = {}
        self.decision_method_vars = {}   #decision name -> {method: BooleanVar}
        self._add_decision_menus(calibration_frame, 'calibration')

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
        
        #Name a reference antenna directly, if you already know which one you want.
        #Only for 'manual': the real antenna list isn't known until the MS is read, so
        #leaving this blank picks from the ranking at run time instead.
        ttk.Label(calibration_frame, text="Reference antenna name (optional):", font=("Arial", 10)).pack(anchor="w", pady=(0, 5))
        self.ref_antenna_var = tk.StringVar(value="auto")
        self.ref_antenna_entry = ttk.Entry(
            calibration_frame,
            textvariable=self.ref_antenna_var,
            width=30,
            state='disabled'
        )
        self.ref_antenna_entry.pack(anchor="w", pady=(0, 15))
        self.decision_vars['refant'].trace_add('write', lambda *_: self.toggle_ref_antenna_entry())

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

        #shallow throwaway clean first, to judge cell/image size/robust on this data
        self.test_image_var = tk.BooleanVar(value=False)
        self.test_image_check = ttk.Checkbutton(
            image_frame,
            text="Make a test image first",
            variable=self.test_image_var
        )
        self.test_image_check.pack(anchor="w", pady=(0, 5))

        ttk.Label(image_frame, text="Robust:", font=("Arial", 10)).pack(anchor="w", pady=(0, 5))
        self.robust_var = tk.DoubleVar(value=CLEAN_ROBUST)
        self.robust_spinbox = ttk.Spinbox(
            image_frame,
            from_=-2.0,
            to=2.0,
            increment=0.5,
            textvariable=self.robust_var,
            width=30
        )
        self.robust_spinbox.pack(anchor="w", pady=(0, 5))

        ttk.Label(image_frame, text="Deconvolver", font=("Arial", 10)).pack(anchor="w", pady=(0, 5))
        self.deconvolver = tk.StringVar(value="mtmfs")
        self.deconvolver_options = ["mtmfs","hogbom", "clark", "multiscale","mem","clarkstokes","asp"]
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

        #imaging-side decision dropdowns (self-cal, baseline cal)
        self._add_decision_menus(image_frame, 'image')

        ttk.Label(image_frame, text="Self Calibration Cycles:", font=("Arial", 10)).pack(anchor="w", pady=(0, 5))
        self.self_cal_cycle_var = tk.IntVar(value=SELF_CAL_DEFAULT_CYCLES)
        self.self_cal_cycle_spinbox = ttk.Spinbox(
            image_frame,
            from_=0,
            to=4096,
            textvariable=self.self_cal_cycle_var,
            width=10,
            state='disabled'
        )
        self.self_cal_cycle_spinbox.pack(anchor="w", pady=(0, 5))
        #cycles are only meaningful while self-cal is on
        self.decision_vars['self_cal'].trace_add('write', lambda *_: self.toggle_self_cal_entry())


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
    
    def _add_decision_menus(self, frame, group):
        """Render a labelled mode dropdown for each DECISIONS entry in `group`, plus a
        method multi-select beneath any entry that declares one."""
        for name, spec in DECISIONS.items():
            if spec.get('gui') != group:
                continue
            ttk.Label(frame, text=f"{spec['label']}:", font=("Arial", 10)).pack(anchor="w", pady=(0, 5))
            var = tk.StringVar(value=spec['default'])
            self.decision_vars[name] = var
            ttk.Combobox(
                frame,
                textvariable=var,
                values=list(spec['modes']),
                state="readonly",
                width=30
            ).pack(anchor="w", pady=(0, 5) if spec.get('methods') else (0, 15))
            if spec.get('methods'):
                self._add_method_checks(frame, name, spec)

    def _add_method_checks(self, frame, name, spec):
        """Checkbutton per method of decision `name`, disabled while its mode is off."""
        box = ttk.Frame(frame)
        box.pack(anchor="w", padx=(15, 0), pady=(0, 15))
        self.decision_method_vars[name] = {}
        for method, description in spec['methods'].items():
            var = tk.BooleanVar(value=method in spec['methods_default'])
            self.decision_method_vars[name][method] = var
            ttk.Checkbutton(box, text=description, variable=var).pack(anchor="w")
        self.decision_vars[name].trace_add(
            'write', lambda *_, n=name, b=box: self.toggle_method_checks(n, b))

    def toggle_method_checks(self, name, box):
        """Grey out a decision's method checkboxes when its mode is off."""
        state = "disabled" if self.decision_vars[name].get() == OFF else "normal"
        for child in box.winfo_children():
            child.config(state=state)

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

    def toggle_ref_antenna_entry(self):
        """Naming an antenna only means anything when refant is not on auto."""
        manual = self.decision_vars['refant'].get() != AUTO
        self.ref_antenna_entry.config(state="normal" if manual else "disabled")
        if not manual:
            self.ref_antenna_var.set(AUTO)

    def toggle_self_cal_entry(self):
        """Cycles only apply while self-cal is on."""
        on = self.decision_vars['self_cal'].get() != OFF
        self.self_cal_cycle_spinbox.config(state="normal" if on else "disabled")

    def submit(self):
        """Collect every option into the summary dict the pipeline imports."""
        decisions_chosen = {name: var.get() for name, var in self.decision_vars.items()}
        #<decision>_methods matches the Options field name, so no per-decision special case
        method_choices = {f"{name}_methods": [m for m, var in methods.items() if var.get()]
                          for name, methods in self.decision_method_vars.items()}
        source_info = self.app.source_data
        self_cal_on = decisions_chosen['self_cal'] != OFF

        # Create summary dictionary
        summary_dict = {
            "source": source_info['source'],
            "archive_file": source_info['file'],
            "archive_files": source_info.get('files') or [],
            "band": source_info['band'],
            "source_ra": source_info['source_ra'],
            "source_decl": source_info['source_decl'],
            "search_alias": source_info['search_alias'],
            "redshift": source_info.get('redshift', ''),
            "proj_code": source_info.get('proj_code', ''),
            "decisions": decisions_chosen,
            "solint": self.solint_var.get(),
            "reference_antenna": self.ref_antenna_var.get(),
            "min_snr": self.snr_var.get(),
            "image_filename": self.image_filename_var.get() if self.use_custom_naming_var.get() else None,
            "image_size": [self.image_size_var.get(),self.image_size_var.get()],
            "interactive_image": self.interactive_var.get(),
            "use_custom_cell_size": self.use_custom_cell_var.get(),
            "cell_size": self.cell_size_var.get() if self.use_custom_cell_var.get() else None,
            "deconvolver":self.deconvolver.get(),
            "weighting":self.weighting.get(),
            "robust":self.robust_var.get(),
            "test_image":self.test_image_var.get(),
            "self_cal_cycles":self.self_cal_cycle_var.get() if self_cal_on else None,
            **method_choices,
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
