#!/bin/bash

# Remove .log and listobs files
find . -type f -name "*.log" -delete
find . -type f -name "*-listobs.txt" -delete

# Remove .ms directories
find . -type d -name "*.ms" -exec rm -rf {} +
find . -type d -name "source.ms" -exec rm -rf {} +
find . -type d -name "initial.ms" -exec rm -rf {} +

# Remove .ms.flagversion directories
find . -type d -name "*.ms.flagversions" -exec rm -rf {} +

# Remove .G0,B0 directories
find . -type d -name "*.G*" -exec rm -rf {} +
find . -type d -name "*.B0" -exec rm -rf {} +
find . -type d -name "*.fluxscale*" -exec rm -rf {} +
find . -type d -name "*.selfcal*" -exec rm -rf {} +

#remove images
find . -type d -name "*.tt0" -exec rm -rf {} +
find . -type d -name "*.mask" -exec rm -rf {} +
find . -type d -name "TempLattice*" -exec rm -rf {} +

#remove pb and pbcorimage
find . -type d -name "*.pb" -exec rm -rf {} +
find . -type d -name "*.pbcorimage" -exec rm -rf {} +

echo "Cleanup completed: removed .log, .ms, and .ms.flagversion files"