
def install_dependencies():
    """Install required Google API client libraries."""
    import subprocess
    import sys

    print("Checking and installing dependencies...")
    print("Installing CASA dependencies...")
    subprocess.check_call([sys.executable, "-m", "pip", "install","--quiet", "--upgrade"
                           ,"casatools","casatasks","casaviewer","casaplotms","casashell"])
    print("Installing required Google API client libraries...")
    subprocess.check_call([sys.executable, "-m", "pip", "install","--quiet", "--upgrade"
                           ,"google-api-python-client", "google-auth-httplib2", "google-auth-oauthlib",
                           ])
    print("Installation complete.")

def create_virtual_environment(env_name="my_virtual_env"):
  """
  Creates a new Python virtual environment.
  Args:
      env_name (str): The name of the virtual environment to create.
                      This will also be the name of the directory.
  """
  import subprocess

  #Bash Script to create venv
  script_path = "./scripts/venv_setup.sh"

  try:
    # Execute the Bash script
    # check=True will raise a CalledProcessError if the script exits with a non-zero status (error)
    # capture_output=True will capture stdout and stderr
    result = subprocess.run([script_path], check=True, capture_output=True, text=True)
    # Print the output from the Bash script
    print("Bash script output:")
    print(result.stdout)
    # Print any errors from the Bash script
    if result.stderr:
      print("Bash script errors:")
      print(result.stderr)
  except subprocess.CalledProcessError as e:
    print(f"Error executing Bash script: {e}")
    print(f"Stdout: {e.stdout}")
    print(f"Stderr: {e.stderr}")
  except FileNotFoundError:
    print(f"Error: Bash script not found at {script_path}")

def install_dep_call():
  '''Wrapper to check for venv and install dependencies, use in main scripts'''
  import sys
  #check may not be working :shrug:p
  if sys.prefix != sys.base_prefix:
    print("Virtual environment detected.")
  else:
    print("No virtual environment detected. creating a venv...")
    create_virtual_environment(env_name=".hvla_env")
  #Installing dependencies to venv!
  install_dependencies()

if __name__ == "__main__":
  import sys
  #check may not be working :shrug:p
  if sys.prefix != sys.base_prefix:
    print("Virtual environment detected.")
  else:
    print("No virtual environment detected. creating a venv...")
    create_virtual_environment(env_name=".hvla_env")
  #Installing dependencies to venv!
  install_dependencies()