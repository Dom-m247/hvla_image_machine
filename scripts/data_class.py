from casatasks import casalog
import sys

class data:
  """contains all the parameters, and options"""
  '''values for Dictionary keys:
  source, bands, breakpoints'''

  def __init__(self):
    self.options = {} #creates empty object, so they can be added dynamically for multiple data sets

  def add_dict(self,dict_in):
    #add logger output
    if dict_in is None:
      print("Warning: dict_in is None, skipping update")
      return False
    try:
      self.options.update(dict_in)
      casalog.post(f"Options added: {self.get_dict()}") #logging values added to data_set object
      return True
    except ValueError as e:
      print(f"an error occured adding an option: {e}")
      sys.exit()

  def get_dict(self):
    """returns options dictrionary"""
    return self.options
