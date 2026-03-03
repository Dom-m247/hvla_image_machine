# Welcome! Pardon my dust this is still under construction, 
use `git clone https://github.com/domo4448/hvla_image_machine` to get all components.

currently it's as simply as running run.sh with python 3.10 installed.
`bash run.sh`
 *note*: update run.sh's `CPU_CORES` variable to allign with your system's specifics.
a dedicated environment will be created to run the script and these cores will be utilized everytime

any successful run through will create an import.json, which can be imported with the arg `--import` to recreate the same steps
 `bash run.sh --import`
  a blank example is available in parsing_examples

if running locally, without prior installations of CASA, 
  in src/HVLA_image_machine.py, under `update_config()` uncomment where noted.

also ask for credentials.json!

