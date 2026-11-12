"""One importvla in a process of its own: run by hvla_data_cal.run_importvla, which reads
the JSON line this prints. A failed import cannot leave stale tables in the parent's cache."""
import json
import sys
from pathlib import Path


def main(argv):
  args = json.loads(argv[1])
  import casatasks as ct
  import casatools
  own_log = ct.casalog.logfile()
  if args.get('logfile') and Path(args['logfile']).resolve() != Path(own_log).resolve():
    ct.casalog.setlogfile(args['logfile'])
    Path(own_log).unlink(missing_ok=True)
  error = ''
  try:
    ct.importvla(**args['kwargs'])
  except Exception as exc:
    error = ' '.join(str(exc).split()) or type(exc).__name__
  finally:
    flush_table_cache(casatools)
  print(json.dumps({'error': error}), flush=True)


def flush_table_cache(casatools):
  """Write every table still in the cache to disk and release its locks."""
  tb = casatools.table()
  for name in tb.showcache() or []:
    try:
      tb.open(name, nomodify=False)
      tb.flush()
      tb.close()
    except Exception:
      pass
  tb.clearlocks()


if __name__ == '__main__':
  main(sys.argv)
