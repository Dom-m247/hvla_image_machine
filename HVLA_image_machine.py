from scripts import Dependencies, gmail_data_fetch, hvla_gui
from casatasks import casalog
#import sys
class data:
  """contains all the parameters, and options"""
  def __init__(self):
    pass #creates empty object, so they can be added dynamically for multiple data sets
  def add_dict(self,dict_in):
    for key, value in dict_in.items():
      #add logger output
      setattr(self, key, value)
      casalog.post(f"Data obj key: {key} to {value}")

def main(argv=None):
  """ Main function to run the HVLA Image Machine application."""
  if argv != None:
    #future use for command line args for command line version
    pass
  print("Welcome to the HVLA Image Machine!")
  
  #check for dependencies and install if needed, including venv setup
  Dependencies.install_dep_call() 
  #sign in to gmail and get token
  token = gmail_data_fetch.generateToken()

  #get source Data from user
  source = data()
  source.add_dict(hvla_gui.run_hvla_app())
  #log options dict for tracking
  
  #get archive from email
  #gmail_data_fetch.get_archive(token)


if __name__ == "__main__":
  main()