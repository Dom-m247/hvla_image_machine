#a script to automate installation of dependencies on new instances
def install_dependencies():
    """Install required Google API client libraries."""
    import subprocess
    import sys

    print("Checking and installing dependencies...")
    print("checking CASA dependencies...")
    subprocess.check_call([sys.executable, "-m", "pip", "install","--quiet", "--upgrade"
                           ,"casatools","casatasks","casaviewer","casaplotms","casashell"])
    print("checking  Google API client libraries...")
    subprocess.check_call([sys.executable, "-m", "pip", "install","--quiet", "--upgrade"
                           ,"google-api-python-client", "google-auth-httplib2", "google-auth-oauthlib",
                           ])
    print("Installation verified/complete.")


def install_dep_call():
  '''Wrapper to check for venv and install dependencies, use in main scripts'''
  import sys
  #check may not be working :shrug:p
  if sys.prefix != sys.base_prefix:
    print("Virtual environment detected.")
  else:
    print("No virtual environment detected. Please run start_up_script.sh")
    return
  #Installing dependencies to venv!
  install_dependencies()

if __name__ == "__main__":
  import sys
  #check may not be working :shrug:p
  if sys.prefix != sys.base_prefix:
    print("Virtual environment detected.")
  else:
    print("No virtual environment detected. creating a venv...")
  #Installing dependencies to venv!
  install_dependencies()