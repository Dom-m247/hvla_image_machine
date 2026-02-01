from casatasks import casalog  # type: ignore
import sys
from classes.observations_class import Obs_data
#from classes.source_class import source_info
from pre_calibration.constants import *
import pprint

class Options:
  """contains all the parameters, and options"""
  '''values for Dictionary keys:
  source, bands, breakpoints'''

  def __init__(self, 
               source=None,
               archive_file = '',
               band='auto',
               breakpoints=[],
               custom_amp_cal='auto',
               reference_antenna='auto',
               min_snr=3.0,):
    #default members
    self.source = source
    self.archive_file = archive_file
    self.band = band
    self.breakpoints = breakpoints
    self.custom_amp_cal = custom_amp_cal
    self.reference_antenna = reference_antenna
    self.min_snr = min_snr
  
    #other members 
    #fileNames
    self.initial_calibration_filename = '' #ms/calbration tables include phase,amp and target
    self.calibrated_filename = '' #file name of calibrated source standalone MS

    self.observation_data = Obs_data() 
    #source_classe objects
    self.source_ids = None
    self.amp_cal = None
    self.phase_cal = None
    self.init_data = Obs_data()
    #extra members added during processing for tracking 
    self.ref_ant = None
    self.split_observations = None
    # validate inputs below; else throw err 
       
  def process_input_dict(self,dict_in):
    """import options from dict's (from import.json/GUI/Terminal)"""
    if dict_in is None:
      print("Warning: input options is None, skipping update")
      return False
    try:
      self.source = dict_in['source']
      self.archive_file = dict_in['archive_file']
      self.band = dict_in['band']
      self.breakpoints = dict_in['breakpoints']
      self.custom_amp_cal = dict_in['custom_amp_cal']
      self.reference_antenna = dict_in['reference_antenna']
      self.min_snr = dict_in['min_snr']
      self.image_filename = dict_in['image_filename']
      self.image_size = dict_in['image_size']
      self.interactive_image = dict_in['interactive_image']
      self.use_custom_cell_size = dict_in['use_custom_cell_size']
      if self.use_custom_cell_size:
        self.cell_size = dict_in['cell_size']
      self.deconvolver = dict_in['deconvolver']
      self.weighting = dict_in['weighting']
      self.do_self_cal = dict_in['do_self_cal']
      if self.do_self_cal:
        self.self_cal_cycles = dict_in['self_cal_cycles']
      casalog.post(f"Information added to obj: {dict_in}") #logging values added to data_set object
      return True
    except ValueError as e:
      print(f"an error occured processing an option: {e}")
      sys.exit()
    except KeyError as ke:
      print(f"Key Error processing options: {ke}")
      sys.exit()

  def to_dict(self):
    summary_dict = {}
    summary_dict.update(self.__dict__)
    summary_dict.update({'amp_cal':self.amp_cal.to_dict()})
    summary_dict.update({'source_ids':self.source_ids.to_dict()})  
    summary_dict.update({'phase_cal':self.amp_cal.to_dict()})
    summary_dict.update({'observation_data':self.observation_data.to_dict()})
    summary_dict.update({'init_data':self.init_data.to_dict()})
    summary_dict.pop('split_observations',None)
    return summary_dict
  
  def generate_dict(self):
    '''generate a dictionarly to output to json for generating import'''
    summary_dict = {}
    summary_dict.update({'source':self.source})
    summary_dict.update({'archive_file':self.archive_file})
    summary_dict.update({'band':self.band})
    summary_dict.update({'breakpoints':self.breakpoints})
    summary_dict.update({'custom_amp_cal':self.custom_amp_cal})
    summary_dict.update({'reference_antenna':self.reference_antenna})
    summary_dict.update({'min_snr':self.min_snr})
    summary_dict.update({'image_filename':self.image_filename})
    summary_dict.update({'image_size':self.image_size})
    summary_dict.update({'interactive_image':self.interactive_image})
    summary_dict.update({'use_custom_cell_size':self.use_custom_cell_size})
    if self.use_custom_cell_size:
      summary_dict.update({'cell_size':self.cell_size})
    summary_dict.update({'deconvolver':self.deconvolver})
    summary_dict.update({'weighting':self.weighting})
    summary_dict.update({'do_self_cal':self.do_self_cal})
    if self.do_self_cal:
      summary_dict.update({'self_cal_cycles':self.self_cal_cycles})
    return summary_dict
  
  def generate_debug_dict(self):
    '''add extra data found - Defunct?'''
    print(f"YYOOOOOO GENERATE_DEBUG_DICT WAS RAN BROOOOOOOO")
    summary_dict = self.generate_dict() 
    summary_dict.update({'amp_cal_source':self.amp_cal_source})
    summary_dict.update({'observation_data':self.observation_data}) 
    summary_dict.update({'init_data':self.init_data})


