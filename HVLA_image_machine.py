from scripts import Dependencies, data_fetch

def main():
  print("Welcome to the HVLA Image Machine!")
  #check for dependencies and install if needed, including venv setup
  Dependencies.install_dep_call() 
  #get archive to email
  data_fetch.get_archive()


if __name__ == "__main__":
  main()