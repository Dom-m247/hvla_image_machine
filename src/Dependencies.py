##a script to automate installation of dependencies on new instances
"""Dependencies.py: A script to manage and install required Python dependencies for the HVLA Image Machine application."""
import subprocess
import sys

def install_from_requirements():
  """Install all modules from requirements.txt file."""
  #requirments.txt *Should* be in the same directory as this script
  #if it's not then
  print(f"verifying all modules from requirments.txt...")
  try:
      subprocess.check_call([sys.executable, "-m", "pip", "install",'--quiet', "-r", "requirements.txt"])
      print("All modules from requirements.txt installed successfully.")
      return True
  except subprocess.CalledProcessError as e:
      print(f"Error installing modules: {e}")
      return False


def install_dep_call():
  '''Wrapper to check for venv and install dependencies, use in main scripts'''
  #check may not be working :shrug:p
  if sys.prefix != sys.base_prefix:
    print("Virtual environment detected.")
  else:
    print("No virtual environment detected. Please run start_up_script.sh")
    sys.exit()
  #Installing dependencies to venv!
  if not install_from_requirements():
    print("Error installing dependencies from requirements.txt, script not proceding.")
    sys.exit()

if __name__ == "__main__":
  install_dep_call()