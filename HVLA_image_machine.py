from scripts import Dependencies, gmail_data_fetch, hvla_gui,hvla_data_cal
from scripts.data_class import data

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
  source.add_dict(hvla_gui.run_hvla_app()) #opens GUI and gets user input

  #TODO:archive download here/in GUI app/other module

  #Start data calibration  
  hvla_data_cal.data_cal(source)



  
if __name__ == "__main__":
  main()