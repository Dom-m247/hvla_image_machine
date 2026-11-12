'''runner.stop_leftovers on real processes named like the ones a run leaves behind.'''
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from harness import runner


class StopLeftovers(unittest.TestCase):
  def spawn(self, cwd, name):
    '''A sleeping process whose comm is `name`, working in cwd.'''
    exe = Path(cwd) / name
    shutil.copy(shutil.which('sleep'), exe)
    proc = subprocess.Popen([str(exe), '300'], cwd=cwd)
    self.addCleanup(proc.kill)
    return proc

  def test_only_named_processes_in_the_run_dir_are_stopped(self):
    with tempfile.TemporaryDirectory() as run, tempfile.TemporaryDirectory() as other:
      Path(run, 'sub').mkdir()
      viewer = self.spawn(Path(run, 'sub'), 'casaviewer')
      xvfb = self.spawn(run, 'Xvfb')
      elsewhere = self.spawn(other, 'casaviewer')
      unrelated = self.spawn(run, 'casalogger')
      self.assertEqual(runner.stop_leftovers(run, grace=2), 2)
      self.assertIsNotNone(viewer.wait(timeout=5))
      self.assertIsNotNone(xvfb.wait(timeout=5))
      self.assertIsNone(elsewhere.poll())
      self.assertIsNone(unrelated.poll())

  def test_nothing_to_stop(self):
    with tempfile.TemporaryDirectory() as run:
      self.assertEqual(runner.stop_leftovers(run), 0)


if __name__ == '__main__':
  unittest.main()
