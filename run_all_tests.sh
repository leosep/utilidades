#!/bin/sh
# Run the tests of the five projects. The interface tests need a display:
# on Linux xvfb-run is used when it is installed (sudo apt install xvfb python3-tk).
set -e
cd "$(dirname "$0")"
runner=""
command -v xvfb-run >/dev/null 2>&1 && runner="xvfb-run -a"
for project in 01-billcutter 02-vault 04-finance 05-branchchat; do
  echo "== $project"
  (cd "$project" && $runner python3 -m unittest discover -s tests 2>&1 | tail -3)
done
echo "== 03-photo-cleaner"
(cd 03-photo-cleaner && node tests/exif.test.js)
