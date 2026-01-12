#Replace "sources" with fields to allow for broader searching!
import casatasks as ct

from pre_calibration.options_class import Options
from pre_calibration.constants import *
from pprint import pprint as pp

def in_spw(listobs_spw,test_band):
  '''checks if a spw is within a range'''
              #lower range      upper range
  return True if (listobs_spw >= test_band[0]) and (listobs_spw <= test_band[1]) else False

def find_bands(data):
  """find which bands the spw are in"""
  detected_bands = []
  #extract the spw in mhz
  for each_spw in data.get_dict()["spectral_windows"]:
    for test_band,value in BAND_MHZ_RANGES.items():
      if in_spw(each_spw["ch0_mhz"],value):
        if test_band not in detected_bands:
          detected_bands.append(test_band)
  if detected_bands is None:
    raise ValueError("No bands were found in the MS")
  return detected_bands

def asses_spw(data):
  '''checks if the SPW matches the input *and* define for model if auto'''
  given_band = data.get_dict_sp("band") #bands?
  detected_bands = find_bands(data)
  if len(detected_bands) > 1:
    raise Exception("More than one band detected, Not yet implemented.")
  if given_band == "auto":
    newDict = {"band": detected_bands[0]}
    data.add_dict(newDict) #should replace "auto" in band with the right band
  if given_band != detected_bands[0]:
    ct.casalog.post(f"The selected band: \"{given_band}\" doesn't match detected bands: {detected_bands}")

def verify_model(data):
  '''
    verify that the amp calibrator alligns with the selceted Band
    May become unecessary if archive is downloaded
  '''
  pass

def set_Models(data):
  '''generates model names based of found amp calibrators'''
  #TODO:add support for bands as a list
  ampCal = (data.get_dict())["amp_cal_source"]
  ampCalModel = ampCal + '_' + data.get_dict()["band"]
  newDict = {"model": ampCalModel}
  data.add_dict(newDict)

def get_source_ID(data):
  '''termial input for non-standard sources - TODO: manual Flux input'''
  #try simbad? #ADD ME FOR VERIFICATION/CUSTOM SOURCES!
  #get amp_cal source ID from user!
  #TEMP RE_WRITE TO USE GUI!
  numSources = 1
  print("Sources")
  sources = data.get_dict()["sources"]
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

def check_source_manual(data,sourceID):
  '''checks that the manually entered sourceID is in the observation'''
  for source in data.get_dict()["sources"]:
    if source["name"] == sourceID:
      ct.casalog.post("Amp Cal found, ID:{sourceID}")
      data.add_dict({"amp_cal_source":'{sourceID}'})
      return True
    else:
      return None

def check_source(options:Options):
  '''checks for any common amp calibrators are in sources TODO: change to fields?'''
  sources = options.observation_data.sources
  for i in range(len(sources)):
    for amp_cal in COMMON_AMPCALS_DICT:
      if sources[i].name == amp_cal:
        ct.casalog.post('Amp Cal found, ID:{amp_cal}, {COMMON_AMPCALS_DICT[amp_cal]}')
        options.amp_cal_source = {'amp_cal_3c':COMMON_AMPCALS_DICT[amp_cal],
                                  'amp_cal':amp_cal}
        return True
  return False    
      
def find_amp_cal(options:Options):
  #TODO: upgrade to utilize other "better" claibrators
  '''Checks that a useable amp calibrator is present'''
  if options.custom_amp_cal == "Yes":
    sourceID = get_source_ID(options)
    check_source_manual(options,sourceID)
    return
  check_source(options)
  asses_spw(options)
  set_Models(options)
  verify_model(options)
  
  #returns to hvla_data_cal.py
  