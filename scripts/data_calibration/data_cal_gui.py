##############BROKEN#######

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
#from find_calibrators import * 

class AmpCalWindow:
# Main container for source input and info
  def __init__(self, master, app):
    self.master = master
    self.app = app
    #establish window properties (random af nums lol)
    master.title("Amp Calibrator Input")
    master.geometry("600x400")
    master.minsize(400, 400)

    # Main container for source input and info
    main_container = ttk.Frame(master)
    main_container.pack(fill="both", expand=True, padx=10, pady=10)

    # Source Input Frame (left side)
    source_frame = ttk.LabelFrame(main_container, text="Amp Cal Input", padding=10)
    source_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))

    # Source name label and entry
    ttk.Label(source_frame, text="Enter source name:", font=("Arial", 20)).pack(anchor="w", pady=(0, 5))
    self.source_var = tk.StringVar()
    self.source_entry = ttk.Entry(source_frame, textvariable=self.source_var, width=30, font=("Arial", 10))
    self.source_entry.pack(anchor="w", pady=(0, 10))
    # Trace source_var to enable Get Observations button when text is entered
    self.source_var.trace("w", self.on_source_change)

    # Source Info Frame (right side)
    info_frame = ttk.LabelFrame(main_container, text="Source Information", padding=10)
    info_frame.pack(side="right", fill="both", expand=True, padx=(5, 0))
    
    # Info display text widget
    self.info_text = tk.Text(info_frame, height=15, width=30, state="disabled", wrap="word")
    self.info_text.pack(fill="both", expand=True, pady=(0, 10))

    button_frame = ttk.Frame(master)
    button_frame.pack(fill="x", padx=15, pady=10)

    # Validate button
    self.validate_button = ttk.Button(
        source_frame, 
        text="Check Valid Source", 
        command=self.validate_source
    )
    self.validate_button.pack(anchor="w", pady=(0, 5))
    self.source_validated = False

    self.submit_source_button = ttk.Button(
        button_frame,
        text="Submit",
        command=self.submit_amp_cal,
        state="disabled"
    ).pack(side="right", padx=5)
    
    ttk.Button(
        button_frame,
        text="Cancel",
        command=master.quit
    ).pack(side="right")
    messagebox.showwarning("Automation Error", "Please enter a amp cal source ID")
        
    
  def on_source_change(self, *args):
    """Disable Get Observations button when source text changes"""
    self.source_validated = False
    self.submit_source_button.config(state="disabled")
    

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
    self.submit_source_button.config(state="normal")
    
    # Display source info
    self.display_source_info(source)

  def display_source_info(self, source):
    """Display validated source information"""
    info_content = f"""Source Information:\n\nName: {source}\n\nStatus: Validated ✓
    \nBand: {self.band_var.get()}\n\nLast Updated: N/A\n\nObservations: N/A\n\nCoordinates: N/A"""
    self.info_text.config(state="normal")
    self.info_text.delete("1.0", "end")
    self.info_text.insert("1.0", info_content)
    self.info_text.config(state="disabled")
  def submit_amp_cal(self):
    """Move to the breakpoints window"""
    source = self.source_var.get()
    band = self.band_var.get()
    
    if not source.strip() and not self.selected_file:
        messagebox.showwarning("Input Required", "Please enter a valid amp calibration source")
        return
    
    # Store the data from Simbad Here
    self.app.source_data = {
        "source": source,
        "band": band,
        "file": self.selected_file
    }
    
    # Close this window and open breakpoints window
    self.master.quit()
    self.master.destroy()
      
  
class AMPCALApp():
    def __init__(self):
        self.root = None
        self.source_data = {}
        self.create_ampCal_window()

    def create_ampCal_window(self):
        """Create the breakpoints selection window"""
        self.root = tk.Tk()
        self.ampCal_window = AmpCalWindow(self.root, self)
        self.root.mainloop()


def run_ampCal_app(options):
    app = AMPCALApp()
    
    
if __name__ == "__main__":
  options = {"test":1, "test2":2}
  app = AMPCALApp()
  #app.create_ampCal_window()