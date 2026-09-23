##a script to automate installation of dependencies on new instances
"""Dependencies.py: A script to manage and install required Python dependencies for the HVLA Image Machine application."""
import subprocess
import sys
from pathlib import Path

#<root>/src/Dependencies.py -> <root>/requirements.txt, so the install works from
#any working directory
REQUIREMENTS = Path(__file__).resolve().parent.parent / "requirements.txt"

def install_from_requirements():
  """Install all modules from requirements.txt file."""
  print(f"verifying all modules from requirments.txt...")
  try:
      subprocess.check_call([sys.executable, "-m", "pip", "install",'--quiet', "-r", str(REQUIREMENTS)])
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