from __future__ import annotations

from pre_calibration.constants import *
import casatasks as ct
from pre_calibration import options_class
from classes import *
import pprint as pp
from data_calibration import parse_listobs as parse

from pathlib import Path
import threading
import sys
import time

def gain_cal(options:options_class.Options):
  """
  Perform gain calibration on the amplitude calibrator data
  """
  find_refant(options)
  if not Path(GAINCAL_G0ALL).is_dir():
    #define fields in init.ms
    fields = str(options.amp_cal.initial_ms_fieldID)+","+str(options.source_ids.initial_ms_fieldID)

    gaincal_output = ct.gaincal(vis=AMP_CAL_MS+'.ms',
                                caltable=GAINCAL_G0ALL,
                                field=fields, #make intelligent
                                spw='',      #leave blank for all spws option
                                solint='int', 
                                refant=options.ref_ant,
                                calmode='p',
                                gaintype='G',
                                minsnr=options.min_snr,
                                append=False,
                                parang=False)
    
  #bandpass cal
  if not Path(BANDPASS_B0).is_dir():
    print(f"Performing Bandpass...")
    bandpass_output = ct.bandpass(vis=AMP_CAL_MS+'.ms',
                                  caltable=BANDPASS_B0,
                                  field=str(options.amp_cal.initial_ms_fieldID),
                                  spw='',
                                  refant=options.ref_ant,
                                  solint='inf',
                                  bandtype='B',
                                  combine='scan',
                                  gaintable=[GAINCAL_G0ALL],
    )
  #possible flagging_breakpoint here
  #2nd gain cal passes
  if not Path(GAINCAL_G1).is_dir():
    gaincal_output2 = ct.gaincal(vis=AMP_CAL_MS+'.ms',
                               caltable=GAINCAL_G1,
                               field=str(options.amp_cal.initial_ms_fieldID),
                               spw='', 
                               solint='inf',
                               refant=options.ref_ant,
                               gaintype='G',
                               calmode='ap',
                               solnorm=False,
                               gaintable=[BANDPASS_B0],
                               interp=['nearest']
     )
    #apply to source
    gaincal_out3 = ct.gaincal(vis=AMP_CAL_MS+'.ms',
                            caltable=GAINCAL_G1,
                            field=str(options.source_ids.initial_ms_fieldID),
                            spw='',
                            solint='inf',
                            refant=options.ref_ant,
                            gaintype='G',
                            calmode='ap',
                            solnorm=False,
                            gaintable=[BANDPASS_B0],
                            append=True
   )
  if not Path(FLUXSCALE_X+'1').is_dir():
    #transfer flux to amp cal
    print(f"applying flux scale to source...")
    fluxScale_out = ct.fluxscale(vis=AMP_CAL_MS+'.ms',
                            caltable=GAINCAL_G1,
                            fluxtable=FLUXSCALE_X + '1',
                            reference=[str(options.amp_cal.initial_ms_fieldID)],
                            transfer=[str(options.source_ids.initial_ms_fieldID)], #phase cal ?,
                            incremental=False
   )
  print(f"Applying Calibrations to science source...")
  print(f"applying calibration to field ID: {options.source_ids.initial_ms_fieldID}")
  apply_cal_out = ct.applycal(vis=AMP_CAL_MS+'.ms',
           field=str(options.source_ids.initial_ms_fieldID),
           gaintable=[FLUXSCALE_X+'1',BANDPASS_B0],
           interp=['nearest',''], #['nearest','linear']?
           calwt=[False], #true?
           parang=False
  )

  #return to data_data_cal and split of callibrated data
  


 
  
def find_refant(options:options_class.Options):
  """
  Identify the reference antenna for calibration
  """
  anntennas_list = parse.antennas_distance(options) #sorted list of antennas by distance 
  options.ref_ant = anntennas_list[2]['id'] #closest antenna by name ie "VA01"

def check_refant(options,gaincal_out):
  """
  Check which reference antenna was used in gaincal, for future gaincal calls
  """
  pass

