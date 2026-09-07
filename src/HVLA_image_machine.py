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
from classes import call_recorder
from classes import run_log
from archive import form_submission, results_package
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
  parser.add_argument('--no-ms-tar', action='store_true', help='skip taring the calibrated MS (the large bundle); the products tarball is still written')
  arguments = parser.parse_args()
  if arguments.radio_search:
    arguments.cli = True
  return arguments

def main(): #argv
  """ Main function to run the HVLA Image Machine application."""
  print("Welcome to the HVLA Image Machine!")
  source = Options()
  source.sysArgs = argumentManager()
  #--archive: either archive a finished results folder and stop, or fall through
  #and archive this run once it has one.
  if source.sysArgs.archive:
    folder = form_submission.prompt_for_folder()
    if folder:
      form_submission.archive_existing(folder)
      return

  #===========================================================================================  
  #update casa_config measurments
  #update_config()  ####UNCOMMENT HERE ON FIRST USE###
  #===========================================================================================

  delete_logs()
  #record every CASA task call so we can emit a standalone replay.py of the exact
  #process at the end (parameters resolved to literals; no decision logic).
  call_recorder.start()
  #accumulate the human-readable report of what this run decided (see classes/run_log)
  run_log.start()

  if source.sysArgs.importRun:
    # Import mode - skip GUI
    try:
      imported_setting = import_settings.import_options()

      source.process_input_dict(imported_setting)
      #If the imported run used interactive cleaning but carries no saved mask (e.g. an
      #older import.json), offer to supply one so the drawn regions can be replayed.
      if getattr(source, 'interactive_image', False) and not getattr(source, 'mask', ''):
        resp = input("Imported run used interactive cleaning but has no saved mask.\n"
                     "Enter a path to a .mask (or region file) to replay it, "
                     "or press enter to clean interactively: ").strip()
        if resp:
          source.mask = resp
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
  run_log.timing('Calibration', elapsed_time)

  #tcleaning!
  cleaner = Cleaner()
  #every self_cal mode runs image_gen: it no-ops the cycles when off, and prompts
  #through them when guided.
  print(f"Starting Clean")
  start_time = time.perf_counter()
  cleaner.image_gen(source)
  end_time = time.perf_counter()
  elapsed_time = end_time - start_time
  print(f"Imaging Time taken: {elapsed_time:.4f} seconds")
  casatasks.casalog.post(f"Imaging Time taken: {elapsed_time:.4f} seconds")
  run_log.timing('Imaging', elapsed_time)

  #output options obj as json! #CHANGE TO IMPORT
  if not source.sysArgs.noexport:
    import_settings.generate_import(source)
  if source.sysArgs.debug:
    import_settings.generate_debug_export(source,filename="export_for_testing")
  #emit the replay script of the exact CASA calls this run made -> results folder if
  #one was created (collect_results), else the working directory. Best-effort.
  try:
    replay_dir = getattr(source, 'results_dir', '') or '.'
    replay_path = call_recorder.write_replay(Path(replay_dir) / 'replay.py')
    print(f"Wrote replay script: {replay_path}")
  except Exception as e:
    print(f"Could not write replay script: {e}")
  #the human-readable report of the run: what was chosen, and why. Written last so
  #it can describe everything above it, and beside replay.py in the results folder.
  try:
    log_dir = getattr(source, 'results_dir', '') or '.'
    log_name = getattr(source, 'results_name', '') or 'run'
    log_path = run_log.write(source, Path(log_dir) / f"{log_name}.log")
    if log_path:
      print(f"Wrote run log: {log_path}")
  except Exception as e:
    print(f"Could not write run log: {e}")
  #tar the results for the archive form -- after the log and replay, so they are in it
  try:
    results_package.package(source, include_ms=not source.sysArgs.no_ms_tar)
  except Exception as e:
    print(f"Could not package results: {e}")
  #opt-in (--archive): open the archive submission form, prefilled from this run.
  if source.sysArgs.archive:
    form_submission.submit(source)
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

