#!/bin/bash

# Remove .log files
find . -type f -name "*.log" -delete

# Remove .ms directories
find . -type d -name "*.ms" -exec rm -rf {} +

# Remove .ms.flagversion directories
find . -type d -name "*.ms.flagversions" -exec rm -rf {} +

echo "Cleanup completed: removed .log, .ms, and .ms.flagversion files"