from casatasks import casalog
import sys
from classes.observations_class import Obs_data
#from classes.source_class import source_info
from pre_calibration.constants import *


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
               reference_antenna='auto'):
    #default members
    self.source = source
    self.archive_file = archive_file
    self.band = band
    self.breakpoints = breakpoints
    self.custom_amp_cal = custom_amp_cal
    self.reference_antenna = reference_antenna
  
    #other members 
    self.amp_cal = None
    self.observation_data = Obs_data() 

    # validate inputs below; else throw err 
       
  def process_input_dict(self,dict_in):
    #add logger output
    if dict_in is None:
      print("Warning: dict_in is None, skipping update")
      return False
    try:
      self.source = dict_in['source']
      self.archive_file = dict_in['archive_file']
      self.band = dict_in['band']
      self.breakpoints = dict_in['breakpoints']
      self.custom_amp_cal = dict_in['custom_amp_cal']
      self.reference_antenna = dict_in['reference_antenna']
      casalog.post(f"Information added to obj: {dict_in}") #logging values added to data_set object
      return True
    except ValueError as e:
      print(f"an error occured importing an option: {e}")
      sys.exit()
  def to_dict(self):
    summary_dict = {}
    summary_dict.update(self.__dict__)
    summary_dict.update({'amp_cal':self.amp_cal.to_dict()})
    summary_dict.update({'observation_data':self.observation_data.to_dict()})
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
    return summary_dict
  
  def generate_debug_dict(self):
    '''add extra data found'''
    summary_dict = self.generate_dict() 
    summary_dict.update({'amp_cal_source':self.amp_cal_source.to_dict()})
    summary_dict.update({'observation_data':self.observation_data}) 

