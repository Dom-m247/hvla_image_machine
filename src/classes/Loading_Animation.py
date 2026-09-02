from pathlib import Path
import threading
import sys
import time
from pre_calibration.options_class import Options
from classes.constants import *
from API_integrations.simbad import simbad

class LoadingAnimation:
  @staticmethod
  def performing_action(action: str, target=None, args=()):
    """
    Show an animated line showing an action is being performed with cycling dots.
    If target function is provided, runs it in a thread while animating.

    Args:
      action: Description of the action being performed
      target: Optional callable to run in a thread
      args: Arguments to pass to target function
    """
    if target is not None:
      # Capture any exception raised in the worker so it can be re-raised on the
      # main thread. Without this, a failing target dies silently in the thread
      # and the pipeline carries on, surfacing a misleading downstream error.
      worker_error = []
      def _run():
        try:
          target(*args)
        except BaseException as e:
          worker_error.append(e)

      # Run target in a thread and animate while it's running
      thread = threading.Thread(target=_run)
      thread.start()

      # Animate the dots while thread is alive
      dot_states = ['', '.', '..', '...']
      dot_index = 0
      while thread.is_alive():
        dots = dot_states[dot_index % len(dot_states)]
        sys.stdout.write(f'\rPerforming {action}' + dots.ljust(3))
        sys.stdout.flush()
        time.sleep(0.5)
        dot_index += 1

      thread.join()
      if worker_error:
        sys.stdout.write(f'\rPerforming {action}... Failed!\n')
        sys.stdout.flush()
        raise worker_error[0]
      sys.stdout.write(f'\rPerforming {action}... Done!\n')
      sys.stdout.flush()
    else:
      # Just show the animation cycling
      pass

  @staticmethod
  def plotMS_wait():
    """
    Create an infinite loop that waits till user presses enter on termincal
    """
    try:
      waiting = "Please perform actions In PlotMS. Press Enter to continue..."
      while(input(waiting) != ''):
        time.sleep(0.5)
    except KeyboardInterrupt:
      pass

