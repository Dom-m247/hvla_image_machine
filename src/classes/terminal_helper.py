import threading
import sys
import time

class LoadingAnimation:
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
      # Run target in a thread and animate while it's running
      thread = threading.Thread(target=target, args=args)
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
      sys.stdout.write(f'\rPerforming {action}... Done!\n')
      sys.stdout.flush()
    else:
      # Just show the animation cycling
      pass
      #dot_states = ['', '.', '..', '...']
      #for dot_index in range(12):  # Cycle through dots 3 times
      #  dots = dot_states[dot_index % len(dot_states)]
      #  sys.stdout.write(f'\rPerforming {action}' + dots.ljust(3))
      #  sys.stdout.flush()
      #  time.sleep(0.5)
      #sys.stdout.write('\n')
      #sys.stdout.flush()

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

