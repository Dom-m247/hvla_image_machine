#handles importing/exporting setting/data to json file
from .data_class import data
from casatasks import casalog
import json,sys
FOLDER_NAME = "hvla_script_proj"

def add_path(archivePath):
  """localize path to archive name"""
  sysPath = sys.path[0]
  archivePath = sysPath[:sys.path[0].find(FOLDER_NAME)] + archivePath
  print(f"{archivePath}")
  return archivePath
  

def revmove_path(archivePath):
  """delocalize archive file"""
  archivePath = archivePath[archivePath.find(FOLDER_NAME):]
  return archivePath

def import_options():
  """imports the options stored in import.json"""
  try:
    file_path = "import.json"
    # Open the file in read mode ('r')
    with open(file_path, 'r') as file:
      # Use json.load() to parse the file content into a Python object (usually a dictionary or a list)
      data_dict = json.load(file)
      data_dict['archive_file'] = add_path(data_dict['archive_file'])
      print("options imported Sucessfully")
      return data_dict
  except FileNotFoundError:
    print(f"Error: The file '{file_path}' was not found.")
  except json.JSONDecodeError:
    print(f"Error: Could not decode JSON from the file '{file_path}'. Check for syntax errors in the JSON file.")
  except Exception as e:
    print(f"An unexpected error occurred: {e}")
  #finally:
    #an execption occured trying to use an import, ending
    #print("An error occured trying to Import settings.")
    #sys.exit()

def genereate_import(data_obj):
  """generates an importable options data class file"""
  if data_obj is None: 
    #checks for empty data?
    raise ValueError("Empty Data for generating Import file.")
  try:
    #de-pathify archive.file
    dataToSerialize = data_obj.get_dict()
    dataToSerialize['archive_file'] = revmove_path(dataToSerialize['archive_file'])
    with open("export_for_testing.json","w") as json_file: # MODIFIED FOR TESTING
       json.dump(dataToSerialize,json_file,indent=4)
  except RuntimeError as e:
    print("error exporting to json") 

if __name__ == "__main__":
  '''Testing'''
  data_obj = data()
  testDict = {
    "archive_file" : "/hvla_script_proj/data_archive/AL727/observation.54757.0577199/AL727_1_54757.05772_54757.55622.exp",
    "bands" : "All_Bands",
    "breakPoints" : ["Manual Flagging", "image Gen"]
  }
  data_obj.add_dict(testDict)
  genereate_import(data_obj)
  data_test = import_options()