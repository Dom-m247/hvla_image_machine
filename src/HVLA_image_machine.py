import sys,os
import casaviewer
import casatasks
import casaconfig
from pre_calibration.options_class import Options
from pre_calibration import *
from image_generation.image_maker import Cleaner
#from archive_dowload import *
import pprint
import time
from pathlib import Path

def main(argv):
  """ Main function to run the HVLA Image Machine application."""
  print("Welcome to the HVLA Image Machine!")
  #update casa_config measurments 
  update_config()
  #sign in to gmail and get token
  #token = gmail_options_fetch.generateToken()
  
  delete_logs()

  if len(argv) > 1 and argv[1] == "import":
    # Import mode - skip GUI
    try:
      imported_setting = import_settings.import_options()
      source = Options()
      source.process_input_dict(imported_setting)
    except FileNotFoundError as error:
      print(f"The import does not exist.{error}")
  else:
    # Normal GUI mode
    try:
      #get source options from user
      options = hvla_gui.run_hvla_app()
      if options is None: #opens GUI and gets user input
        raise RuntimeError("No options were selected, Exiting")
      source = Options()
      source.process_input_dict(options)
    except RuntimeError as e:
      print(f"{e}")
      sys.exit()
  
  #TODO:archive download here/in GUI app/other module 
  #if sourceID = somthing, run scraper routine
  #try:
  #Start options calibration  
  start_time = time.perf_counter()
  hvla_data_cal.data_calibration(source)
  end_time = time.perf_counter()
  elapsed_time = end_time - start_time
  print(f"Calibration Time taken: {elapsed_time:.4f} seconds")

  #tcleaning!
  cleaner = Cleaner()
  if not 'manual_clean' in  source.breakpoints:
    print(f"Starting Clean")
    start_time = time.perf_counter()
    cleaner.image_gen(source)
    end_time = time.perf_counter()
    elapsed_time = end_time - start_time
    print(f"Imaging Time taken: {elapsed_time:.4f} seconds")
    casatasks.casalog.post(f"Imaging Time taken: {elapsed_time:.4f} seconds")
  else:
    print(f"Starting Manual Clean and self_cal")
    image = Cleaner.manual_clean(options=source)

  #output options obj as json! #CHANGE TO IMPORT
  import_settings.generate_import(source)
  import_settings.generate_debug_export(source,filename="export_for_testing")
  #if 'display_image' in source.breakpoints and not 'manual_clean' in source.breakpoints:
  # casaviewer.imview(raster=(source.image_filename)+'.image.tt0')   
  print("Completed Successfuly. Exiting...")
  
  
  #except Exception as e:
    #generate debug export, then exit
  #  export_obj(source,e)
    

def export_obj(options,error):
  print(f"Generating a debug export becuase of error : {error}")
  import_settings.generate_debug_export(options,filename="error_export")

def delete_logs():
  """ Deleting casa logs that aren't the most recent one
  stolen fom 1.99 """ 
  import os 
  timestamp_integers = []
  for item in os.listdir(): 
    newest = False
    if item.startswith("casa-"):
      timestamp_integers.append(int(item[5:13] + item[14:20]))
  timestamp_integers = sorted(timestamp_integers)
  for i in range(len(timestamp_integers) - 1):
    item = 'casa-' + str(timestamp_integers[i])[:8] + '-' + str(timestamp_integers[i])[8:14] + '.log'
    os.remove(os.path.join(item)) # deleting casa logs

def update_config():
  #if first time startup
  #casaconfig.measures_update() #UNCOMMENT HERE ON FIRST USE
  return

if __name__ == "__main__":
  main(sys.argv)

  #casatasks.tclean(vis='3c391_ctm_mosaic_spw0.ms',imagename='3c391_ctm_spw0_ms_I',
  #    field='',spw='',
  #    specmode='mfs',
  #    niter=500,
  #    gain=0.1,threshold='1mJy',
  #    gridder='mosaic',
  #    deconvolver='multiscale',
  #    scales=[0, 5, 15, 45],smallscalebias=0.9,
  #    interactive=True,
  #    imsize=[480,480],cell=['2.5arcsec','2.5arcsec'],
  #    stokes='I',
  #    weighting='briggs',robust=0.5,
  #    pbcor=False,
  #    savemodel='modelcolumn')
  #casatasks.tclean(vis='3c391_ctm_mosaic_spw0.ms',imagename='3c391_ctm_spw0_multiscale',
  #    field='',spw='',
  #    specmode='mfs',
  #    niter=20000,
  #    gain=0.1, threshold='1.0mJy',
  #    gridder='mosaic',
  #    deconvolver='multiscale',
  #    scales=[0, 5, 15, 45], smallscalebias=0.9,
  #    interactive=True,
  #    imsize=[480,480], cell=['2.5arcsec','2.5arcsec'],
  #    stokes='I',
  #    weighting='briggs',robust=0.5,
  #    pbcor=False,
  #    savemodel='modelcolumn')