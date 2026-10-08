'''One participant in test_gate.py, run as its own interpreter from the repo root:
python -m tests.query.gate_child <scenario> <state> <cache> <log> [args]'''
import json
import os
import sys
import time
from pathlib import Path

from API_integrations import catalog_client as cc

from .support import FakeResp

scenario, state, cache, log_path = sys.argv[1:5]
extra = sys.argv[5:]
cc.STATE_PATH = state
cc.CACHE_PATH = Path(cache)

def log(event, **kw):
  with open(log_path, 'a') as f:
    f.write(json.dumps({'pid': os.getpid(), 'event': event, 't': cc._now_ns(), **kw}) + '\n')

def no_network(*a, **kw):
  raise AssertionError('real request attempted')
cc._session.request = no_network

if scenario == 'twice':
  for _ in range(2):
    with cc.slot('t') as s:
      log('stamp', stamp=s.state['last_send_ns'])

elif scenario == 'hold':
  with cc.slot('t') as s:
    log('stamp', stamp=s.state['last_send_ns'])
    time.sleep(float(extra[0]))

elif scenario == 'once':
  log('start')
  with cc.slot('t') as s:
    log('stamp', stamp=s.state['last_send_ns'])

elif scenario == 'cooldown':
  with cc.slot('t') as s:
    s.cool_down(60)
    log('stamp', stamp=s.state['last_send_ns'])

elif scenario == 'try':
  try:
    with cc.slot('t'):
      log('entered')
  except cc.Unavailable as e:
    log('unavailable', msg=str(e))

elif scenario == 'recheck_raises':
  try:
    with cc.slot('t', recheck=lambda: 1 / 0):
      pass
  except ZeroDivisionError:
    log('raised')
  time.sleep(20)

elif scenario == 'unpaced':
  cc.PACE_REQUESTS = False
  for _ in range(2):
    log('want')
    with cc.slot('t') as s:
      log('enter', stamp=s.state['last_send_ns'])
      time.sleep(2)
      log('exit')

elif scenario == 'lookup':
  body = Path(extra[0]).read_bytes()
  def fake_request(method, url, **kw):
    log('send', url=url, params=kw.get('params'))
    time.sleep(1)
    return FakeResp(200, body)
  cc._session.request = fake_request
  log('result', result=cc.ned_lookup(extra[1]))
