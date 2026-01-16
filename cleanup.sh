#!/bin/bash

# Remove .log files
find . -type f -name "*.log" -delete

# Remove .ms directories
find . -type d -name "*.ms" -exec rm -rf {} +

# Remove .ms.flagversion directories
find . -type d -name "*.ms.flagversions" -exec rm -rf {} +

# Remove .G0,B0 directories
find . -type d -name "*.G0" -exec rm -rf {} +
find . -type d -name "*.B0" -exec rm -rf {} +
find . -type d -name "*.G0all" -exec rm -rf {} +

echo "Cleanup completed: removed .log, .ms, and .ms.flagversion files"