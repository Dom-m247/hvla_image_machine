# Welcome! this is still underconstruction, 
currently it's as simply as running strart_up_script.sh, 
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
  - support back button autopopulate

###### import support 
  - add frame for using imported setting (supports ms/exp (test MS support))
  - ~~de-absolute-path import.json ~~
    - check if archive in import exists,
      - if no archive, pull the intended archive!?
  - add "populate" with imported settings etc.
  - "export" modified for testing
#### Breakpoints 
  - actually mark sensible breakpoints!
  - synconize Breakpoint list (pulls from 3 different list and dicts oops)
  - add phase/amp/phase-amp cal options!

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
  - add support for multiple bands!
  - **phase Calibration**
###### Parse_list_obs
  - turn scan data into time data types

### Archival
  - use XML data to populate?

### Planning/Orginization
 - figure out the "proper" way to have "global" constants? I,E project name for Import_set.py
 - Unit Testing???
 - Fix variable/function nameing conventions, Incositinet is ***BAD***

### maintainability steps
 - Excessive commenting!
 - maintin example copies of parsed external data 
  - I.e Email formats, web page layouts, casa log formatting

### Bugs 
- in ~~Breakpoint~~ source selection gui, ~~submit~~ close requires it being pressed twice.
- fix error "2025-12-29 20:47:31     SEVERE  ::casa  measures_update: the measures data at /home/user/.casa/data is not maintained by casaconfig and so it can not be updated unless force is True"
# Possible issues
- Any instances of path access fucked up by calling script from outside active dir?
  - (at runtime, set path to correct folder)

# Tech - Exploration
EC2 instance for web-server to Open an endpoint \
accept request, w/ pysocket, pass ssh from nrao to user as request response 