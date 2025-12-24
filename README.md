# Welcome! this is still underconstruction, 
currently it's as simply as running strart_up_script.sh, 
also ask for credentials.json!

# TODO
### Gui?? 
#### Source Input
  - validate Bands 
  - simbad source validation logic
  - allow for multiple observation import, -> dict?
  - implement NRAO archive interaction
    - pools NRAO servers and returns list of observations
      - get selection from user.

  -set existing file preference if a source is selcted -> disable source info fill from start, populate from MS? -> have "get observations" button run routine similar to "radio_search" which auto populates the selected file with the downloaded archive.
#### Breakpoints 
  - actually mark sensible breakpoints!

### gmail grabber - Maybe not necessary
  - Note: vlaArchive does have credential
  - automate login with browser nav for dedicated archive email?
  - add sha verification
### logger
  - currently passing through any loging to casalog, may need to spin off??
- browser navigation
### HVLA_data_cal
  - paramaterize vla_import for multiple arcives
### Archival
  - use XML data to populate?

### maintainability steps
 - Excessive commenting!
 - maintin example copies of parsed external data 
  - I.e Email formats, web page layouts, casa log formatting

### Bugs 
- in Breakpoint gui, submit requires it being pressed twice.
