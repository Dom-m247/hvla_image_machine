#!/bin/bash
find . -type d -name "*.tt0*" -exec rm -rf {} +
find . -type d -name "*.mask" -exec rm -rf {} +
find . -type d -name "*.pbcorimage" -exec rm -rf {} +
find . -type d -name "*.selfcal*" -exec rm -rf {} +
