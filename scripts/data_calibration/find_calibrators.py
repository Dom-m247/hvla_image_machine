#Replace "sources" with fields to allow for broader searching!

import casatasks as ct

from ..data_class import data
from ..constants import *
from pprint import pprint as pp

def verify_model(options):
  '''verify that the amp calibrator alligns with the selceted Band
    May become unecessary if archive is downloaded'''
  pass

def set_Models(options):
  '''generates model names based of found amp calibrators'''
  ampCal = (options.get_dict())["amp_cal_source"]
  ampCalModel = ampCal + "_" + options.get_dict()["bands"]
  newDict = {"model": ampCalModel}
  options.add_dict(newDict)

def get_source_ID(options):
  '''termial input for non-standard sources - TODO: manual Flux input'''
  #try simbad? #ADD ME FOR VERIFICATION/CUSTOM SOURCES!
  #get amp_cal source ID from user!
  #TEMP RE_WRITE TO USE GUI!
  numSources = 1
  print("Sources")
  sources = options.get_dict()["sources"]
  for source in sources:
    name = source["name"]
    print(f"{numSources}: {name} ")
    numSources+=1
  valid_sourceID = False
  while valid_sourceID is False:
    try:
      sourceID = int(input("Enter source number: "))
      if (sourceID) <= numSources-1 and (sourceID) > 0:
        valid_sourceID = True
    except ValueError:
      print("cannot convert to integer, try again")
  for count, (source) in enumerate(sources):
    if count+1 == sourceID: 
      sourceID = source["name"]
      print(sourceID)
      return sourceID

def check_source_manual(options,sourceID):
  '''checks that the manually entered sourceID is in the observation'''
  for source in options.get_dict()["sources"]:
    if source["name"] == sourceID:
      ct.casalog.post("Amp Cal found, ID:{sourceID}")
      options.add_dict({"amp_cal_source":"{sourceID}"})
      return True
    else:
      return None

def check_source(options):
  '''checks for any common amp calibrators are in sources TODO: change to fields?'''
  for source in options.get_dict()["sources"]:
    for key in COMMON_AMPCALS_DICT:
      if source["name"] == key:
        ct.casalog.post("Amp Cal found, ID:{key}, {COMMON_AMPCALS_DICT[key]}")
        newDict = {"amp_cal_source":COMMON_AMPCALS_DICT[key]}
        options.add_dict(newDict)
        
        return True
  return False    
      
def find_amp_cal(options):
  '''Checks that a useable amp calibrator is present'''
  if options.get_dict()["custom_amp_cal"] == "Yes":
    print("here")
    sourceID = get_source_ID(options)
    check_source_manual(options,sourceID)
    return
  check_source(options)
  set_Models(options)
  verify_model(options)
  #split calibrators?
  #next
  #PROGRESS! 
  