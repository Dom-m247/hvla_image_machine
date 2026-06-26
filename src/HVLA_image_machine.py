import sys,os,argparse
import casaviewer
import casatasks 
import casaconfig
from classes.CLI_input import CLI
from pre_calibration.options_class import Options
from pre_calibration import *
from image_generation.image_maker import Cleaner
from archive_dowload.radio_search_integration import RadioSearchIntegration, DelosDownload
from data_calibration import hvla_data_cal
#from archive_dowload import *
import pprint
import threading
import time
from pathlib import Path

def argumentManager():
  '''for ArgParse'''
  #do a -auto that will trigger fallback options for calibselection
  parser = argparse.ArgumentParser(description="HVLA Image Machine", allow_abbrev=True)
  parser.add_argument('--radio_search','-rs', action='store_true', help='search for and download archives using radio_search script. Will also run in cli mode')
  parser.add_argument('--importRun','-i','-import', action='store_true', help='import from json file for auto-run')
  parser.add_argument('--noexport', action='store_true', help='export options to json file')
  parser.add_argument('--debug', action='store_true', help='use debug exports for testing')
  parser.add_argument('--cli','-c','-t', action='store_true', help='run whole script in cli mode without GUI')
  parser.add_argument('--cliCalib','-tc', action='store_true', help='run cli for calibration and imaging, allows user over-ride on calibrators')
  parser.add_argument('--archive','-a', action='store_true', help='run archiving routine')
  arguments = parser.parse_args()
  if arguments.radio_search:
    arguments.cli = True
  return arguments

def main(): #argv
  """ Main function to run the HVLA Image Machine application."""
  print("Welcome to the HVLA Image Machine!")
  source = Options()
  source.sysArgs = argumentManager()
  #update casa_config measurments 
  #update_config()  ####UNCOMMENT HERE ON FIRST USE###

  #sign in to gmail and get token
  #token = gmail_options_fetch.generateToken()

  delete_logs()
  
  if source.sysArgs.importRun:
    print("importingWorks???")
    # Import mode - skip GUI
    try:
      imported_setting = import_settings.import_options()
      
      source.process_input_dict(imported_setting)
    except FileNotFoundError as error:
      print(f"The import does not exist.{error}")
  elif source.sysArgs.cli and not source.sysArgs.cliCalib:
    if source.sysArgs.radio_search:
      radio_search(source) #gets source_name + band + archive
    else:
      #print("Running in cli mode without GUI. ###NOT YET fully IMPLEMENTED")
      #get source options from user
      CLI.getOptions(source)
  else: #not parser.importRun and not parser.cli:
    # Normal GUI mode
    try:
      #get source options from user
      options = hvla_gui.run_hvla_app()
      if options is None: #opens GUI and gets user input
        raise RuntimeError("No options were selected, Exiting")
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
  if 'manual_clean' not in source.breakpoints:
    print(f"Starting Clean")
    start_time = time.perf_counter()
    cleaner.image_gen(source)
    end_time = time.perf_counter()
    elapsed_time = end_time - start_time
    print(f"Imaging Time taken: {elapsed_time:.4f} seconds")
    casatasks.casalog.post(f"Imaging Time taken: {elapsed_time:.4f} seconds")
  else:
    print(f"Starting Manual Clean and self_cal")
    image = Cleaner.manual_clean_calibration(options=source)

  #output options obj as json! #CHANGE TO IMPORT
  if not source.sysArgs.noexport:
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
  casaconfig.measures_update()
  return

def radio_search(options:Options):
  """Utilize radio_search to find archives, then download them while gathering
  calibration info in parallel."""
  #not yet fully implemented, Utilizes Internal tool to search and download observation archives
  if not options.sysArgs.radio_search:
    return
  #find and select the observation; returns the archive file(s) to download from the NAS
  download_files = RadioSearchIntegration.perform_radio_search(options)

  #split control: one thread downloads the files from the NAS (DelosDownload),
  #another gathers CLI calibration info. Wait for both before returning to main.
  downloader = DelosDownload(download_files, options)
  download_thread = threading.Thread(target=downloader.run)
  calibration_thread = threading.Thread(target=CLI.getCalibrationOptions, args=(options,))
  download_thread.start()
  calibration_thread.start()
  download_thread.join()
  calibration_thread.join()
  #surface any error from the download worker (thread exceptions are otherwise lost);
  #stop here rather than letting importvla fail later on missing input files.
  if downloader.error is not None:
    print(f"\nArchive download failed: {downloader.error}")
    raise downloader.error
  #report downloads from the main thread (after the prompts finish) so the output
  #doesn't interleave with the interactive calibration input()
  if options.archive_files:
    print(f"\nDownloaded {len(options.archive_files)} archive file(s):")
    for path in options.archive_files:
      print(f"  {path}")
  else:
    print("\nWarning: no archive files were downloaded (DelosDownload returned nothing).")
  

if __name__ == "__main__":
  main()#sys.argv


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