# Welcome! this is still underconstruction, 
currently it's as simply as running run.sh with python 3.10 installed.
`bash run.sh`
 *note* update run.sh's `CPU_CORES` variable to allign with your system's specifics.
a dedicated environment will be created to run the script and utilized everytime

any successful run through will create an import.json, which can be imported with the arg `import` to recreate the same steps
 `bash run.sh import`

if running locally, without prior installations of CASA, 
  in src/HVLA_image_machine.py, under `update_config()` uncomment where noted.

also ask for credentials.json!


# TODO
- GUI improvments + features todo
  - number of self-cal iteration
  - delineate "manual self-cal + cleaning" from interactive cleaning
- Automatic Features to implement 
  - Gaussian fitting
  - core subratraction
  - PlotMS breakpointing 
    - use a loop to wait for terminal input to continue (?)
- Things to classify(turn to classes)
 - image (imstat) return for parsing -> new module Image analysis
 - sperate user options into options and per run *data* class (heirarcy?)
- Archiving
  - info from user:
    - email, name, reason for reducting
    - num knots + lobes, and notes about result
  - implement data collection for:
    - problems encountered while calibrating (statistics?)
    - (m) redshift
    - () # of any calibration round 

### maintainability steps
 - Excessive commenting!
 - maintin example copies of parsed external data 
  - I.e Email formats, web page layouts, casa log formatting

### Bugs 
- in ~~Breakpoint~~ source selection gui, ~~submit~~ close requires it being pressed twice.
- ##### Race Conditions present
  - plotms doesn't pause,
  - Split/import don't pause either
- if list-obs formating is inconsitient  (ex. epoch and srcID running into each other) 

# Possible issues
- Any instances of path access messed up by calling script from outside active dir?
  - (at runtime, set path to correct folder)

# Tech - Exploration
EC2 instance for web-server to Open an endpoint \
accept request, w/ pysocket, pass ssh from nrao to user as request response 
 - import nrao calibrator list to automatically find and fill many more calibrators