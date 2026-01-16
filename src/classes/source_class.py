import casatasks as ct # type: ignore

#from pre_calibration.options_class import Options 
from classes.observations_class import Obs_data 
from pre_calibration.constants import *

TYPE_AMP_CAL = 'amp_calibrator'
TYPE_TARGET = 'target'
AUTO = 'auto'

class source_info:
  #TODO: upgrade to utilize other "better" claibrators
  def __init__(self,options,type="",name=""):
    self.type = type
    self.name3c = ''
    self.name = name
    self.sourceID = ''
    
    if self.type == TYPE_AMP_CAL and options.custom_amp_cal == AUTO:
      if not self.detect_amp_cal(options):
        raise Exception("No amp Calibrator was detected")
      self.bands = self.asses_spw(options)
      #set Model name
      self.model = self.name3c + "_" + self.bands  +".im" #not included here for c-string cast later
    elif self.type == TYPE_AMP_CAL and options.custom_amp_cal != AUTO:
      self.manual_amp_cal(options)
    elif self.type == TYPE_TARGET:
      self.name = options.source
      self.sourceID = self.find_sourceID(options)
    self.fieldID = self.find_fieldID(options.observation_data)

    #extra members defined by initial ms split
    self.initial_ms_fieldID = ''
  
  def find_fieldID(self,data_source):
    for field in data_source.fields:
      if field.name == self.name: 
        return field.id
      
  def find_sourceID(self, options):
    """find sourceID from source name"""
    for source in options.observation_data.sources:
      if source.name == options.source:
        return source.id
    raise Exception(f"Source {options.source} not found in observation")
  
  def find_bands(self,options):
    detected_bands = []
    if options.band == AUTO:
      for each_spw in options.observation_data.spectral_windows:
        for test_band,value in BAND_MHZ_RANGES.items():
          if self.in_spw(each_spw.ch0_mhz,value):
            if test_band not in detected_bands:
              detected_bands.append(test_band)
    else: 
      return options.band
    return detected_bands
  
  def asses_spw(self,options):
    '''checks if the SPW matches the input *and* define for model if auto'''
    band_option = options.band
    detected_bands = self.find_bands(options)
    if len(detected_bands) > 1:
      raise Exception("More than one band detected, Not yet implemented.")
    if band_option == "auto":
      return detected_bands[0]
    if band_option != detected_bands[0]:
      ct.casalog.post(f"The selected band: \"{band_option}\" doesn't match detected bands: {detected_bands}")

  def in_spw(self,listobs_spw,test_band):
    '''checks if a spw is within a range'''
                #lower range      upper range
    return True if (listobs_spw >= test_band[0]) and (listobs_spw <= test_band[1]) else False
    
  def detect_amp_cal(self,options):
    sources = options.observation_data.sources
    for i in range(len(sources)):
      for amp_cal in COMMON_AMPCALS_DICT:
        if sources[i].name == amp_cal:
          ct.casalog.post('Amp Cal found, ID:{amp_cal}, {COMMON_AMPCALS_DICT[amp_cal]}')
          self.name3c = COMMON_AMPCALS_DICT[amp_cal]
          self.name = amp_cal
          self.sourceID = sources[i].id
          return True
    return False
  
  def manual_amp_cal(self,options):
    pass
  #def check_source_manual(data,sourceID):
  #  '''checks that the manually entered sourceID is in the observation'''
  #  for source in data.get_dict()["sources"]:
  #    if source["name"] == sourceID:
  #      ct.casalog.post("Amp Cal found, ID:{sourceID}")
  #      data.add_dict({"amp_cal_source":'{sourceID}'})
  #      return True
  #    else:
  #      return None

  def verify_model(data):
    '''
      verify that the amp calibrator alligns with the selceted Band
      May become unecessary if archive is downloaded
    '''
    pass
 # def get_source_ID(data):
 #  '''termial input for non-standard sources - TODO: manual Flux input'''
 #  #try simbad? #ADD ME FOR VERIFICATION/CUSTOM SOURCES!
 #  #get amp_cal source ID from user!
 #  #TEMP RE_WRITE TO USE GUI!
 #  numSources = 1
 #  print("Sources")
 #  sources = data.get_dict()["sources"]
 #  for source in sources:
 #    name = source["name"]
 #    print(f"{numSources}: {name} ")
 #    numSources+=1
 #  valid_sourceID = False
 #  while valid_sourceID is False:
 #    try:
 #      sourceID = int(input("Enter source number: "))
 #      if (sourceID) <= numSources-1 and (sourceID) > 0:
 #        valid_sourceID = True
 #    except ValueError:
 #      print("cannot convert to integer, try again")
 #  for count, (source) in enumerate(sources):
 #    if count+1 == sourceID: 
 #      sourceID = source["name"]
 #      print(sourceID)
 #      return sourceID
    
  def to_dict(self):
    return self.__dict__
    
