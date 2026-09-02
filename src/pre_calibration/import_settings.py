#handles importing/exporting setting/data to json file
#from .options_class import Options
#from casatasks import casalog
import argparse, json, sys
from classes.constants import FOLDER_NAME, IMPORT_JSON, RS_IMPORT
from .options_class import Options
import pprint


def _json_default(obj):
  """Fallback JSON encoder for non-serializable Options members (argparse Namespace,
  nested data/source objects, numpy scalars, ...). Keeps export robust as new fields
  are added to Options instead of failing on each newly-introduced type."""
  if isinstance(obj, argparse.Namespace):
    return vars(obj)
  to_dict = getattr(obj, 'to_dict', None)
  if callable(to_dict):
    return to_dict()
  try:
    import numpy as np
    if isinstance(obj, np.generic):
      return obj.item()
    if isinstance(obj, np.ndarray):
      return obj.tolist()
  except ImportError:
    pass
  if hasattr(obj, '__dict__'):
    return vars(obj)
  return str(obj)


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
      #a multi-file segment is stored the same way, one localized path per file
      if data_dict.get('archive_files'):
        data_dict['archive_files'] = [add_path(p) for p in data_dict['archive_files']]
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
    if dataToSerialize.get('archive_files'):
      dataToSerialize['archive_files'] = [revmove_path(p) for p in dataToSerialize['archive_files']]
    with open(filename+".json","w") as json_file: 
       json.dump(dataToSerialize,json_file,indent=4,default=_json_default)
  except Exception as e:
    print(f"error exporting to json: {e}")

def generate_debug_export(data_obj,filename="debug_export"):
  """generates an importable options data class file"""
  if data_obj is None: 
    #checks for empty data?
    raise ValueError("Empty Data for generating debug export file.")
  try:
    #de-pathify archive.file
    dataToSerialize = data_obj.to_dict()
    dataToSerialize['archive_file'] = revmove_path(dataToSerialize['archive_file'])
    if dataToSerialize.get('archive_files'):
      dataToSerialize['archive_files'] = [revmove_path(p) for p in dataToSerialize['archive_files']]
    with open(filename+".json","w") as json_file: 
       json.dump(dataToSerialize,json_file,indent=4,default=_json_default)
  except Exception as e:
    print(f"error exporting to json: {e}")
