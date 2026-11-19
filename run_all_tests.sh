#!/bin/sh
# Run the tests of the five projects. The interface tests need a display: on Linux,
# run_all_tests.py uses xvfb-run when it is installed (sudo apt install xvfb python3-tk).
set -e
cd "$(dirname "$0")"
exec python3 run_all_tests.py
