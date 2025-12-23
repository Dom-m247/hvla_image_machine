# Welcome! this is still underconstruction, 
currently it's as simply as running strart_up_script.sh, 
also ask for credentials.json!

# TODO
- Gui?? 
 - Source Input
  - validate Bands 
  - simbad source validation logic
  - allow for multiple observation import
  - implement NRAO archive interaction
    - pools NRAO servers and returns list of observations
      - get selection from user.
 - Breakpoints 
  - actually mark sensible breakpoints!
  
  - use it as an "options" menu to insert manual break points like flagging data in plotms
    - to fill out while downloading
- gmail grabber - Maybe not necessary
  - Note: vlaArchive does have credential
  - automate login with browser nav for dedicated archive email?
  - add sha verification
- logger
  - currently passing through any loging to casalog, may need to spin off??
- browser navigation
- casa PipeLine
- Archival

### maintainability steps
 - Excessive commenting!
 - maintin example copies of parsed external data 
  - I.e Email formats, web page layouts, casa log formatting

### Bugs 
- in Breakpoint gui, submit requires it being pressed twice.