import casatasks as ct

#from pre_calibration.options_class import Options 
from classes.observations_class import Obs_data 
from pre_calibration.constants import *
import pprint
TYPE_FLUX_CAL = 'flux_calibrator'
TYPE_PHASE_CAL = 'phase_cal'
TYPE_TARGET = 'target'
AUTO = 'auto'

class source_info:
  #TODO: upgrade to utilize other 'better' claibrators
  def __init__(self,options,type='',name=''):
    self.type = type
    self.name = name
    self.source_id = ''
    self.field_id = ''

    if self.type == TYPE_FLUX_CAL and options.custom_amp_cal == AUTO:
      if not self.detect_amp_cal(options):
        raise Exception('No Calibrator was detected for setJy')
    elif self.type == TYPE_PHASE_CAL or (self.type == TYPE_TARGET and self.name is None): #would specifying a phase cal impede this logic?
      #search through fullset observation data and find 2nd most observed field?
      self.detect_by_nrows(options,self.type)
    elif self.type == TYPE_FLUX_CAL and options.custom_amp_cal != AUTO: #Change to Phase Cal? AND or Add phase cla
      self.manual_amp_cal(options)
    elif self.type == TYPE_TARGET and (self.name is not None):
      #a source was specified
      self.name = options.source
      self.source_id = self.find_source_id(options)
      self.field_id = self.find_fieldID(options.observation_data)
    #extra members defined by initial ms split after initilization
    self.initial_ms_fieldID = ''
  
  def find_fieldID(self,data_source):
    for field in data_source.fields:
      if field.name == self.name: 
        return field.id
      
  def find_source_id(self, options):
    '''find source_id from source name'''
    for section in options.observation_data.sources:
      print(f"source | {section}")
      print(f"source.name | {section.name}")
      print(f"options.source | {options}")

      if section.name == options.source:
        return section.id
      else:
        raise Exception(f'Source {options.source} not found in observation')
  
  def detect_by_nrows(self, options, source_type): #may be able to find 'source?'
    fields = options.observation_data.fields
    #pull n_terms
    fields_list = []
    source_field_entry = None
    for i in range(len(fields)):
      curr_field_id = fields[i].id
      curr_field_nrows = fields[i].nrows
      fields_list.append((curr_field_id,curr_field_nrows)) #maybe sketchy, curr_field_id ~= order in op.obs_data.fields or later
    #sort
    sorted_nrows = sorted(fields_list,key = lambda x: x[1],reverse=True) #sort by nrows in tuple
    if source_type == TYPE_TARGET:
      source_position = 0 #the location of the object to be used as a phase calibrator
      source_field_entry = fields[(sorted_nrows[source_position])[0]]
      pass
    if source_type == TYPE_PHASE_CAL:
      phase_cal_position = 1 #the location of the object to be used as a phase calibrator
      source_field_entry = fields[(sorted_nrows[phase_cal_position])[0]] # gets the field ID of the 2nd most observed field
    self.name = source_field_entry.name
    self.source_id = source_field_entry.src_id
    self.field_id = source_field_entry.id

    


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
      raise Exception('More than one band detected, Not yet implemented.')
    if band_option == 'auto':
      options.band = detected_bands[0] 
      return detected_bands[0]
    if band_option != detected_bands[0]:
      ct.casalog.post(f"The selected band: \'{band_option}\' doesn't match detected bands: {detected_bands}")
    return options.band

  def in_spw(self,listobs_spw,test_band):
    '''checks if a spw is within a range'''
                #lower range      upper range
    return True if (listobs_spw >= test_band[0]) and (listobs_spw <= test_band[1]) else False
    
  def detect_amp_cal(self,options):
    '''Finds the (first) Amp/Flux density calibrator in the full ms'''
    fields = options.observation_data.fields
    for i in range(len(fields)):
      for amp_cal in COMMON_AMPCALS_DICT:
        if fields[i].name == amp_cal or fields[i].name == COMMON_AMPCALS_DICT[amp_cal] :
          ct.casalog.post(f'Amp Cal found, ID:{amp_cal}, {COMMON_AMPCALS_DICT[amp_cal]}')
          self.name3c = COMMON_AMPCALS_DICT[amp_cal]
          self.name = fields[i].name
          self.field_id = fields[i].id 
          self.source_id = fields[i].src_id
          self.bands = self.asses_spw(options) 
          self.model = self.name3c + '_' + self.bands  +'.im'
          return True
    return False
  
  def manual_amp_cal(self,options):
    pass
  #def check_source_manual(data,source_id):
  #  '''checks that the manually entered source_id is in the observation'''
  #  for source in data.get_dict()['sources']:
  #    if source['name'] == source_id:
  #      ct.casalog.post('Amp Cal found, ID:{source_id}')
  #      data.add_dict({'amp_cal_source':'{source_id}'})
  #      return True
  #    else:
  #      return None

  def verify_model(data):
    '''
      verify that the amp calibrator alligns with the selceted Band
      May become unecessary if archive is downloaded
    '''
    pass
 
  def to_dict(self):
    return self.__dict__
    
