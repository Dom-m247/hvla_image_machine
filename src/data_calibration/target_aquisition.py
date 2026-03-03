#import casatasks as ct # type: ignore
#
##from ..pre_calibration import options
#from pre_calibration.constants import *
#from pre_calibration.options_class import Options
#from classes.source_class import source_info
#from classes.observations_class import Obs_data


'''
detect a target field
'''


##DEFUNCT: Need to confirm that a given source name IS NOT over written

#def find_field(options):
#  """
#  Determine which fields contain our source
#  closest or longest field from observations?
#  """ 
#  print("Not implemented Good luck")
#  pass
#
#def find_longest_field(obs_fields,options):
#  longest_field = 0
#  for field in obs_fields:
#    if field.nrows > obs_fields[longest_field].nrows:
#      longest_field = field.id
#      
#  return obs_fields[longest_field]
#
#def find_target(options:Options):
#  """
#  Idendtify the field with our target
#  based on longest observation time
#  """
#  source_field = find_longest_field(options.observation_data.fields,options)
#  options.source = source_field.name
#  options.source_ids = source_info(options,"target",source_field.name)
#  options.source_ids.sourceID = source_field.src_id
#
#
#def check_target(options):
#  """
#  check that a source exists, and matches a field(?)"""
#  if options.source is None:
#    find_target(options)
#    return  
#  #find which field target is in
#  find_field(options)
#
#def make_sourceID(options:Options):
#  """create source_info object for target source"""
#  options.source_ids = source_info(options,"target",options.source)
#
#