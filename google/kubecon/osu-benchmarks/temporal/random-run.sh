#!/bin/bash

# Setting up the environment:
# TODO

set -exuo pipefail

# This will be used for a cron job running daily every hour
# 	0 * * * *
HERE=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
source $HERE/env/bin/activate

# This says 2% probability, 3 clusters. The script has hard coded
# that we will do size 16 (so 18 nodes) of c2d-standard-2 for 3 osu metrics
# metrics-16-subset.yaml) for 20x each.
python $HERE/random-run.py -p 2.0 -c 3
