import sys
from scripts import *
from scripts.data_class import data

def main(argv):
  """ Main function to run the HVLA Image Machine application."""
  print("Welcome to the HVLA Image Machine!")

  #check for dependencies and install if needed, including venv setup
  #Dependencies.install_dep_call() 
  #sign in to gmail and get token
  #token = gmail_data_fetch.generateToken()
  source = data()
  delete_logs()

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
      #For checking obj with all options 
      #import_settings.genereate_import(source)
    except RuntimeError as e:
      print(f"{e}")

  #TODO:archive download here/in GUI app/other module 
  #if sourceID = somthing, run scraper routine
  
  #Start data calibration  
  hvla_data_cal.data_cal(source)

  #output data obj as json!
  import_settings.genereate_import(source)

def delete_logs():
  """ Deleting casa logs that aren't the most recent one
  stolen fom 1.99 """ 
  import os 
  timestamp_integers = []
  for item in os.listdir(): 
    newest = False
    if item.startswith("casa-"):
      timestamp_integers.append(int(item[5:13] + item[14:20]))
  timestamp_integers = sorted(timestamp_integers)
  for i in range(len(timestamp_integers) - 1):
    item = 'casa-' + str(timestamp_integers[i])[:8] + '-' + str(timestamp_integers[i])[8:14] + '.log'
    os.remove(os.path.join(item)) # deleting casa logs

if __name__ == "__main__":
  main(sys.argv)