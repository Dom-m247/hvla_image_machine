import sys
from scripts import Dependencies, gmail_data_fetch, hvla_gui,hvla_data_cal,import_settings
from scripts.data_class import data

def main(argv):
  """ Main function to run the HVLA Image Machine application."""
  print("Welcome to the HVLA Image Machine!")

  #check for dependencies and install if needed, including venv setup
  Dependencies.install_dep_call() 
  #sign in to gmail and get token
  #token = gmail_data_fetch.generateToken()
  source = data()

  if len(argv) > 1 and argv[1] == "import":
    # Import mode - skip GUI
    try:
      imported_setting = import_settings.import_options()
      source.add_dict(imported_setting)
    except FileNotFoundError as error:
      print(f"The import does not exist.{error}")
  else:
    # Normal GUI mode
    try:
      #get source Data from user
      if not source.add_dict(hvla_gui.run_hvla_app()): #opens GUI and gets user input
        raise RuntimeError("No options were selected, Exiting")
    except RuntimeError as e:
      print(f"{e}")

  #TODO:archive download here/in GUI app/other modul 
  #Start data calibration  
  hvla_data_cal.data_cal(source)

if __name__ == "__main__":
  main(sys.argv)