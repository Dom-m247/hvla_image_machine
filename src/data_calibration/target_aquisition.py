import casatasks as ct

#from ..pre_calibration import options
from pre_calibration.constants import *

'''
detect a target field
'''

def build_spwID(options):
  """build the spwID for splitting
  TODO: ADD BREAKPOINT CUSTOM SPW?
  """
  spwIDs = ''
  for spw in options.get_dict_sp('spectral_windows'):
    spwIDs = spwIDs + str(spw['id'])
    spwIDs+= ","
  options.add_dict({"spwIDs":spwIDs[:len(spwIDs)-1]})
  

def find_field(options):
  """
  Determine which fields contain our source
  closest or longest field from observations?
  """ 
  print("Not implemented Good luck")
  pass

def define_split_fields(options):
  split_fields = ''
  source = options.get_dict_sp('source')
  amp_cal = options.get_dict_sp('amp_cal_source_id')
  for field in options.get_dict_sp('fields'):
    if field["name"] == source:
      split_fields = split_fields + str(field['id'])
      split_fields += ", "
    if field["src_id"] == amp_cal:
      split_fields = split_fields + str(field['id'])
      split_fields += ", "
  #splitfields = 1,2, 
  options.add_dict({"split1_fields":split_fields[:len(split_fields)-2]}) 


def find_longest_field(obs_fields,options):
  longest_field = 0
  for field in obs_fields:
    if field['nrows'] > obs_fields[longest_field]['nrows']:
      longest_field = field['id']
      
  return obs_fields[longest_field]["name"]

def find_target(options):
  """
  Idendtify the field with our target
  based on longest observation time
  """
  options.add_dict({'source': find_longest_field(options.get_dict_sp("fields"),options)})


def check_target(options):
  """
  check that a source exists, and matches a field(?)"""
  if options.get_dict_sp('source') is None:
    find_target(options)
    return  
  #find which field target is in
  find_field(options)