#manage the dowloading of H/VLA data from https://data.nrao.edu/portal/#/
#google credentials flow adapted from https://developers.google.com/gmail/api/quickstart/python
#
# By Dominic Mello 2025
#NOTE: requires google api client libraries, see Dependencies.py for pip install commands
# PY.10 WILL BE DEPRECATED 10/04/2026!!!

import os.path
from pprint import pprint
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

def generateToken():
  """check if token.json exists, if not create it via OAuth flow, 
    return Credentials object
  """
  creds = None
  # The file token.json stores the user's access and refresh tokens, and is
  # created automatically when the authorization flow completes for the first
  # time.
  if os.path.exists("token.json"):
    creds = Credentials.from_authorized_user_file("token.json", SCOPES)
  # If there are no (valid) credentials available, let the user log in.
  if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
      creds.refresh(Request())
    else:
      #fix with local path to credentials.json
      flow = InstalledAppFlow.from_client_secrets_file(
          "/home/dominic/hvla_script_proj/scripts/credentials.json", SCOPES
      )
      creds = flow.run_local_server(port=0)
    # Save the credentials for the next run
    with open("token.json", "w") as token:
      token.write(creds.to_json())
  return creds

def get_archive_email(service):
  """Return the most recent message dict from do-not-reply@nrao.edu or None."""
  try:
    results = service.users().messages().list(
      userId="me",
      q="from:do-not-reply@nrao.edu",
      maxResults=1
    ).execute()
    messages = results.get("messages", [])
    if not messages:
      return None
    msg_id = messages[0]["id"]
    message = service.users().messages().get(
      userId="me",
      id=msg_id,
      format="full"
    ).execute()
    return message
  except HttpError as error:
    print(f"An error occurred fetching archive email: {error}")
    return None
def clean_email_body(body):
  """Cleans and decodes the email body from base64 and HTML entities."""
  import base64
  import html
  import re

  decoded_body = (base64.urlsafe_b64decode(body)).decode("utf-8")

  # Unescape HTML entities and strip HTML tags (simple approach)
  decoded_body = html.unescape(decoded_body)
  decoded_body = re.sub(r"<[^>]+>", " ", decoded_body)

  # Join lines split with backslash line-continuation and normalize whitespace
  decoded_body = re.sub(r"\\\s*\r?\n\s*", " ", decoded_body)
  decoded_body = re.sub(r"\r?\n", " ", decoded_body)
  decoded_body = re.sub(r"\s+", " ", decoded_body).strip()
  return decoded_body

def get_link(message):
  """Parse the email message to extract download links."""
  import base64
  import re

  body = message["payload"]["body"]["data"]
  decoded_body = (base64.urlsafe_b64decode(body)).decode("utf-8")
  cleaned_body = clean_email_body(body)

  # Find a wget command that includes --reject "index.html*" and --cut-dirs=<num>
  m = re.search(r"(wget\b.*?--reject\s+\"?index\.html\*\"?.*?--cut-dirs=\d+.*?https?://\S+/?)(?:\s|$|['\"])", cleaned_body, re.IGNORECASE)
  if m:
    line = m.group(1).strip()
    SKIP_AHEAD = 2 #to remove indexing ': ' portion
    cmd = line[(line.index(": ")+SKIP_AHEAD):]
    return cmd
  else:
    raise ValueError("No valid download link found in the email body.")
  
def update_wget_command(cmd):
    '''Modify the wget command to specify a download location and not get fetch-all.sh and SUMS'''
    download_location = "data_archive"
    reject_list = "\"index.html*,fetch-all.sh,SHA1SUMS\"" 

    #set download location
    #switch to wget2 for >bigger files, leave for now to cause it to break 
    back_of_cmd = cmd[cmd.index("wget")+4:] 
    fixed_cmd = "wget" + " -P " + download_location + back_of_cmd
    #add fetch-all.sh and SHA1SUMS to reject list
    back_of_cmd = fixed_cmd[fixed_cmd.index("--reject")+22:]
    final_command = fixed_cmd[:fixed_cmd.index("--reject")+9] + reject_list + back_of_cmd

    return final_command

def download_archive(cmd):
  """Execute the wget command to download the archive."""
  import subprocess

  try:
    #add location to wget command
    cmd = update_wget_command(cmd)
    # Execute the wget command
    print("Starting archive download. This will take a moment...")
    result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
    print("Download completed successfully.")
      #print(result.stderr) // output!
  except subprocess.CalledProcessError as e:
    print(f"Error during download: {e}")
    print(f"Stdout: {e.stdout}")
    print(f"Stderr: {e.stderr}") 

def get_archive():
  creds = generateToken()
  try:
    # Call the Gmail API
   service = build("gmail", "v1", credentials=creds)
   message = get_archive_email(service)
   command = get_link(message)
   download_archive(command)
  except HttpError as error:
   # TODO(developer) - Handle errors from gmail API.
   #lmao sure
   print(f"An error occurred with gmail API: {error}")
  except ValueError as ve:
    print(f"error: {ve}")
    return


if __name__ == "__main__":
  get_archive()