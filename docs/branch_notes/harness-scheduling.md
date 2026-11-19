# Branch `harness-scheduling`: what changed and why

Based on `lightcurve-fixes`. Two small changes, both about plumbing, not astronomy:

1. **Sweep scheduling** (`harnesses/harness/sweep.py`): batches are now a work queue.
2. **Archive search helper** (`src/archive_dowload/radio_search_integration.py`): the
   search goes through a local `radio_search` command when the machine has one.

To review: `git diff lightcurve-fixes..harness-scheduling`.

---

## 1. Sweep scheduling: fixed batches → a shared work queue

### Background

A *sweep* is the harness running the pipeline over a list of observations (*selections*).
Each run is a separate pipeline process, takes minutes to hours, and is pinned to its own
set of CPU cores (a *slot*, from `core_slots()`). `batch_size` says how many run at once.

### Before

```python
batches = [selections[i:i + size] for i in range(0, len(selections), size)]
for batch in batches:
    with ThreadPoolExecutor(max_workers=len(batch)) as pool:
        ...                       # start every run in the batch
        results += [f.result() for f in futures]   # wait for ALL of them
```

That is a barrier after every batch. Runs differ in length by a factor of 10 or more (an
old 1980s snapshot vs. a long multi-hour track), so a batch lasted as long as its slowest
run. With `batch_size = 4` and one long track, three slots sat idle for hours.

### After

```python
pending = queue.Queue()               # (index, selection) for every selection
results = [None] * len(selections)

def work(slot):                       # one thread per slot
    while True:
        try:
            index, selection = pending.get_nowait()
        except queue.Empty:
            return
        results[index] = run_one(selection, sweep, slots[slot], ...)

with ThreadPoolExecutor(max_workers=size) as pool:
    for f in [pool.submit(work, s) for s in range(min(size, len(selections)))]:
        f.result()
```

This is a standard worker-pool / work-queue pattern:

- One worker thread per slot. Each keeps its CPU pinning (`slots[slot]`) for every run it
  takes, so two runs never share cores.
- A worker takes the next selection as soon as its last run finishes. A slow run holds up
  only its own slot.
- `results[index] = ...` writes to the slot of the list belonging to that run, so results
  come back **in selection order**, as before. The callers (`report.json`, the lightcurve
  summary) rely on that. Each index is written by exactly one thread, so no lock is needed.
- `queue.Queue` is thread-safe and `get_nowait()` doesn't block, so a worker stops cleanly
  once the queue is empty.
- `f.result()` re-raises any exception from a worker. `run_one` already turns every
  failure into a result rather than raising ("a failure is an event, never an exception
  that ends the sweep"), so in practice this only catches harness bugs.
- Attended presets still use `size = 1`: one run at a time, because a person is at it.

Visible change: the terminal prints `=== Run 3/12 (slot 2): <slug> ===` per run instead of
`=== Batch 1/3 ===`, and one total time at the end.

## 2. `radio_search` helper

### Background

To find observations, the harness asks the NRAO archive through a tool called
`radio_search`. That tool can run only on an NRAO login server, so the pipeline has always
reached it over SSH: `RadioSearch2` logs in with paramiko, using the host, user and path in
`Creds.json`, and runs the tool remotely.

On our group machine there is now a shell command, `/usr/local/bin/radio_search`, that does
the SSH part itself. It takes the same arguments, keeps **one shared SSH connection**
open in the background (OpenSSH `ControlMaster`), so a sweep doesn't log in hundreds of
times. Everyone on the machine uses the same, current copy of the NRAO-side tool. Its usage
text: `radio_search help`.

### The change

- New class `RadioSearchHelper` with the **same interface** as `RadioSearch2`: callable
  with the tool's arguments, returns its stdout as a string, works as a context manager.
  The rest of the code doesn't know which one it got.
- `RadioSearchIntegration`'s factory (the method that used to build `RadioSearch2`) now does:

  ```python
  helper = shutil.which(RADIO_SEARCH_HELPER) if RADIO_SEARCH_HELPER else None
  if helper:
      return RadioSearchHelper(helper)
  ...  # otherwise exactly as before: Creds.json + paramiko
  ```

  So on a machine **without** the command (e.g. your laptop) nothing changes.
  `RADIO_SEARCH_HELPER = ''` switches the helper off everywhere.
- `RadioSearchHelper` runs the command with `subprocess.run`, with:
  - `stdin=DEVNULL` and `SSH_ASKPASS_REQUIRE=never`: an unattended sweep can never hang
    waiting for a password prompt nobody will answer. If no connection is open and no key is
    installed, ssh fails at once and the error message says how to open one.
  - the same 300 s timeout as before, raised as `TimeoutError` (what callers already catch).
  - a non-zero exit with no output → `RuntimeError` (the connection or login failed). If
    there is output, it is returned as the result whatever the exit code, the same as
    `RadioSearch2`, which never looked at the exit code.

## Not changed

No pipeline/science code, presets or file formats. Nothing in the lightcurve output
changes.
