# Welcome! this is still underconstruction, 
currently it's as simply as running run.sh,
any successful run through will create an import.json, which can be used as an arugment
 `bash run.sh import`
 
also ask for credentials.json!


# TODO
### Gui?? 
#### Source Input
  - validate Bands 
  - simbad source validation logic
  - allow for multiple observation imports 
  - implement NRAO archive interaction
    - pools NRAO servers and returns list of observations
      - get selection from user.
  - set existing file preference if a source is selcted -> disable source info fill from start, populate from MS? -> have "get observations" button run routine similar to "radio_search" which auto populates the selected file with the downloaded archive.
  - listify bands -> add multiple band options
    - update calibrators to accept lists!
    - seperate detected bands and selected bands?
  - support back button autopopulate
  - Specify Target
  - specify model with drop down?
  - custum flux value for amp cal?

###### import/export support 
  - add frame for using imported setting (supports ms/exp (test MS support))
   - Partially implemented -> use arg import and have a file "import.json" in the parent directory
  - ~~de-absolute-path import.json ~~
    - check if archive in import exists,
      - if no archive, pull the intended archive!?
  - add "populate" with imported settings etc.
  - "export" modified for testing
  - add timestamp to failed exports?
  - if using imported settings, use included dicts to skip to a point?
    - problems: 
      - missing archive/ms 
      - incorrect archive/ms?
#### Breakpoints 
  - actually mark sensible breakpoints!
  - synconize Breakpoint list (pulls from 3 different list and dicts oops)
  - add phase/~~amp~~/phase-amp cal options!
  - Data-Flagging
   - async issue, plotms doesn't GIL on launch

### gmail grabber - Maybe not necessary
  - Note: vlaArchive does have credential
  - automate login with browser nav for dedicated archive email?
  - add sha verification
### logger
  - auto-delete existing logs? (in 1.99)
  - currently passing through any loging to casalog, may need to spin off??
- browser navigation

### HVLA_data_cal
  - paramaterize vla_import for multiple arcives
  - find_calibrators.py
    - change sources to fields
    - double verify with 2nd mode: observation time (2nd most observed?)
  - add support for multiple bands!
  - store .ms and calibration sets with "intelligent" names -> based on observationn names?
  - **phase Calibration**
  - parrallelize validation?(spw, )
  - Multiple bands with multple models?
  #### Target_acuisition /verification
   - utilize Ra and Declination to verify the target is close to source (stuff radio_search) for incendental obs
   -  closest field to target or longest field from observations?
   - add amp_cal_source_id as a dict!
###### Parse_list_obs
  - turn scan data into time data types
  - lmao observations are broke. Missing cuz of leading whitespace

### Gain calibration

### image Generation
  - 
### Archival
  - use XML data to populate?

### Failover Handling
 - add casa.log copying if error occurs

### Planning/Orginization
 - figure out the "proper" way to have "global" constants? I,E project name for Import_set.py
 - Unit Testing???
 - Fix variable/function nameing conventions, Incositinet is ***BAD***
 - adjust try,exept and Raise handling to fail up to main
 - fix imports to actually follow modularity.
 - add subclass for MS parsed data?
 - add arg to skip to cleaning?
### maintainability steps
 - Excessive commenting!
 - maintin example copies of parsed external data 
  - I.e Email formats, web page layouts, casa log formatting

### Bugs 
- in ~~Breakpoint~~ source selection gui, ~~submit~~ close requires it being pressed twice.
- fix error "2025-12-29 20:47:31     SEVERE  ::casa  measures_update: the measures data at /home/user/.casa/data is not maintained by casaconfig and so it can not be updated unless force is True"
- plotms broken? just wsl?
# Possible issues
- Any instances of path access messed up by calling script from outside active dir?
  - (at runtime, set path to correct folder)

# Tech - Exploration
EC2 instance for web-server to Open an endpoint \
accept request, w/ pysocket, pass ssh from nrao to user as request response 
 - import nrao calibrator list to automatically find and fill many more calibrators