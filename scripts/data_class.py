from casatasks import casalog

class data:
  """contains all the parameters, and options"""
  '''values for Dictionary keys:
  source, bands, breakpoints'''

  def __init__(self):
    pass #creates empty object, so they can be added dynamically for multiple data sets
  def add_dict(self,dict_in):
    for key, value in dict_in.items():
      #add logger output
      setattr(self, key, value)
      casalog.post(f"Data obj key: {key} to {value}") #logging values added to data_set object
