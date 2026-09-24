"""En-masse test harness for the HVLA Image Machine.

Takes one source name, uses radio_search to find every pre-EVLA observation of
it (optionally only those in given projects), downloads each archive segment from
Delos, and drives the pipeline over each hands-free (--importRun) in
configurable parallel batches.

The harness is a *driver*: it reuses the pipeline's own modules for every piece
of real work (NED resolution, radio_search2, archfileinfo parsing, sensitivity
ranking, Delos download, import.json localisation) rather than reimplementing
them, so it exercises the same code the interactive run does.
"""
