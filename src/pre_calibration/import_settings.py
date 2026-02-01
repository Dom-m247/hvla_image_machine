#handles importing/exporting setting/data to json file
#from .options_class import Options
#from casatasks import casalog
import json,sys
from .constants import FOLDER_NAME, IMPORT_JSON, EXPORT_KEYS
from .options_class import Options
import pprint

class ImportHandler():
  pass

def add_path(archivePath):
  """localize path to archive name"""
  sysPath = sys.path[0]
  archivePath = sysPath[:sys.path[0].find(FOLDER_NAME)] + archivePath
  return archivePath
  
def revmove_path(archivePath):
  """delocalize archive file"""
  archivePath = archivePath[archivePath.find(FOLDER_NAME):]
  return archivePath

def import_options():
  """imports the options stored in import.json"""
  try:
    # Open the file in read mode ('r')
    with open(IMPORT_JSON, 'r') as file:
      # Use json.load() to parse the file content into a Python object (usually a dictionary or a list)
      data_dict = json.load(file)
      data_dict['archive_file'] = add_path(data_dict['archive_file'])
      print("options imported Sucessfully")
      return data_dict
  except FileNotFoundError:
    print(f"Error: The file '{IMPORT_JSON}' was not found.")
  except json.JSONDecodeError:
    print(f"Error: Could not decode JSON from the file '{IMPORT_JSON}'. Check for syntax errors in the JSON file.")
  except Exception as e:
    print(f"An unexpected error occurred: {e}")
  #finally:
    #an execption occured trying to use an import, ending
    #print("An error occured trying to Import settings.")
    #sys.exit()

def prepare_dict_export(data:Options):
  """
  extract and compile pertinante info from object for export
  """
  export_dict = data.to_dict()
  for key in EXPORT_KEYS:
    newDict = {key : data.get_dict_sp(key)}
    export_dict.update(newDict)
  return export_dict

def generate_import(data_obj:Options,filename="import"):
  """
  generate the import.json file for another user.
  """
  if data_obj is None: 
    #checks for empty data?
    raise ValueError("Empty Data for generating debug export file.")
  try:
    #de-pathify archive.file
    dataToSerialize = data_obj.generate_dict()
  
    dataToSerialize['archive_file'] = revmove_path(dataToSerialize['archive_file'])
    with open(filename+".json","w") as json_file: 
       json.dump(dataToSerialize,json_file,indent=4)
  except RuntimeError as e:
    print("error exporting to json") 

def generate_debug_export(data_obj,filename="debug_export"):
  """generates an importable options data class file"""
  if data_obj is None: 
    #checks for empty data?
    raise ValueError("Empty Data for generating debug export file.")
  try:
    #de-pathify archive.file
    dataToSerialize = data_obj.to_dict()
    dataToSerialize['archive_file'] = revmove_path(dataToSerialize['archive_file'])
    with open(filename+".json","w") as json_file: 
       json.dump(dataToSerialize,json_file,indent=4)
  except RuntimeError as e:
    print("error exporting to json") 
