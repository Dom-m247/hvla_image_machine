'''Cross-process tests of the catalog_client gate: gate_child scenarios in separate interpreters
sharing one state file. About 90 s, since the interval is real.'''
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from API_integrations import catalog_client as cc

from .support import FIXTURES, FOUND_3C15

REPO = Path(__file__).resolve().parents[2]
S = 10**9
INTERVAL = cc.INTERVAL_NS
WARNING = 'PACE_REQUESTS is off'

def seconds(spans_ns):
  return [round(ns / S, 3) for ns in spans_ns]


class TestGate(unittest.TestCase):
  def setUp(self):
    tmp = tempfile.TemporaryDirectory(prefix='hvla-gate-tests-')
    self.addCleanup(tmp.cleanup)
    d = Path(tmp.name)
    self.state, self.cache, self.log = str(d / 'gate.json'), str(d / 'cache.sqlite'), d / 'log.jsonl'

  def start(self, scenario, *extra):
    p = subprocess.Popen([sys.executable, '-m', 'tests.query.gate_child', scenario, self.state, self.cache,
                          str(self.log), *map(str, extra)],
                         cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    self.addCleanup(self.reap, p)
    return p

  @staticmethod
  def reap(p):
    '''Kill a child the test left running, so a failed test leaves no lock holder behind.'''
    if p.poll() is None:
      p.kill()
      p.wait()
    p.stdout.close()

  def finish(self, *procs):
    '''Each child's output once it exits; a child that crashed fails the test.'''
    outs = []
    for p in procs:
      out, _ = p.communicate(timeout=120)
      self.assertIn(p.returncode, (0, -signal.SIGKILL), f"child exited {p.returncode}:\n{out}")
      outs.append(out)
    return outs

  def events(self, event=None):
    if not self.log.exists():
      return []
    lines = self.log.read_text().split('\n')[:-1]   #a line still being written has no newline yet
    return [r for r in map(json.loads, lines) if event is None or r['event'] == event]

  def wait_for(self, event, n=1, timeout=90):
    end = time.time() + timeout
    while time.time() < end:
      if len(found := self.events(event)) >= n:
        return found
      time.sleep(0.05)
    self.fail(f"no {event!r} event within {timeout} s")

  def test_sends_spaced_across_interpreters(self):
    self.finish(*[self.start('twice') for _ in range(4)])
    stamps = sorted(e['stamp'] for e in self.events('stamp'))
    gaps = [b - a for a, b in zip(stamps, stamps[1:])]
    self.assertEqual(len(stamps), 8)
    self.assertGreaterEqual(min(gaps), INTERVAL, f"gaps={seconds(gaps)}")

  def test_killed_holder_frees_the_lock(self):
    a = self.start('hold', 60)
    stamp_a = self.wait_for('stamp')[0]['stamp']
    time.sleep(1)
    a.send_signal(signal.SIGKILL)
    b = self.start('once')
    self.finish(a, b)
    start_b = self.events('start')[0]['t']
    stamp_b = [e['stamp'] for e in self.events('stamp') if e['stamp'] != stamp_a][0]
    self.assertGreaterEqual(stamp_b - stamp_a, INTERVAL)
    late = stamp_b - max(stamp_a + INTERVAL, start_b)
    self.assertLess(late, S // 2, f"next send {seconds([late])[0]} s later than due")

  def test_deleted_file_makes_the_next_process_wait_the_full_interval(self):
    a = self.start('hold', 3)
    stamp_a = self.wait_for('stamp')[0]['stamp']
    os.unlink(self.state)
    b = self.start('once')
    self.finish(a, b)
    start_b = self.events('start')[0]['t']
    stamp_b = [e['stamp'] for e in self.events('stamp') if e['stamp'] != stamp_a][0]
    self.assertGreaterEqual(stamp_b - start_b, INTERVAL)
    self.assertGreaterEqual(stamp_b - stamp_a, INTERVAL)

  def test_cooldown_is_shared_and_writes_no_stamp(self):
    self.finish(self.start('cooldown'))
    before = json.loads(Path(self.state).read_text())
    self.finish(self.start('try'))
    after = json.loads(Path(self.state).read_text())
    self.assertTrue(self.events('unavailable'))
    self.assertEqual(self.events('entered'), [])
    self.assertEqual(before['last_send_ns'], after['last_send_ns'])

  def test_recheck_lets_one_process_answer_both(self):
    self.finish(*[self.start('lookup', FIXTURES / 'ned_lookup_3C15.xml', '3C 15') for _ in range(2)])
    self.assertEqual(len(self.events('send')), 1)
    self.assertEqual([r['result'] for r in self.events('result')], [FOUND_3C15] * 2)

  def test_exception_in_recheck_releases_the_lock(self):
    a = self.start('recheck_raises')
    self.wait_for('raised')
    self.finish(self.start('once'))
    self.assertIsNone(a.poll(), 'the raiser should still be alive')
    waited = self.events('stamp')[0]['stamp'] - self.events('start')[0]['t']
    self.assertLess(waited, INTERVAL + 3 * S, f"waited {seconds([waited])[0]} s")

  def test_pacing_off(self):
    outs = self.finish(self.start('unpaced'), self.start('unpaced'))
    events = self.events()
    slots = []   #(want, enter, exit) for every slot taken
    for pid in {e['pid'] for e in events}:
      mine = [e for e in events if e['pid'] == pid]
      slots += zip(*([e['t'] for e in mine if e['event'] == k] for k in ('want', 'enter', 'exit')))
    slots.sort(key=lambda s: s[1])
    self.assertEqual(len(slots), 4)
    self.assertFalse(any(nxt[1] < prev[2] for prev, nxt in zip(slots, slots[1:])), 'slots overlap')
    #time each slot waited beyond its own request and the previous holder's release
    waits = [enter - max(want, max((x for _, _, x in slots if x < enter), default=0)) for want, enter, _ in slots]
    self.assertLess(max(waits), S // 2, f"waits={seconds(waits)}")
    self.assertEqual([o.count(WARNING) for o in outs], [1, 1], 'notice once per process')
    #a paced process still waits the interval from the last unpaced stamp
    last = max(e['stamp'] for e in events if e['event'] == 'enter')
    [out] = self.finish(self.start('once'))
    gap = self.events('stamp')[0]['stamp'] - last
    self.assertGreaterEqual(gap, INTERVAL, f"gap={seconds([gap])[0]}")
    self.assertNotIn(WARNING, out)
