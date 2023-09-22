#!/bin/bash

# Setting up the environment:
# this is an e2 shared core (2vcpu, 4GB memory instance with 50GB disk)
# I decided to scp data from there to my local machine instead of git pushing
#
# sudo apt-get update && sudo apt-get install -y git python3-pip python3-venv
# git clone https://github.com/converged-computing/metrics-operator-experiments
# curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" 
# chmod +x ./kubectl
# sudo mv ./kubectl /usr/local/bin/

# Setup env and do a test run
# cd ~/metrics-operator-experiments/google/kubecon/osu-benchmarks/temporal
# python -m venv env
# pip install metricsoperator seaborn pandas
# python3 ./random-run.py -p 2.0 -c 1 --force --project ${GOOGLE_PROJECT}

set -exuo pipefail

# This will be used for a cron job running daily every hour
# 	0 * * * *
HERE=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
source $HERE/env/bin/activate

# This says 2% probability, 3 clusters. The script has hard coded
# that we will do size 16 (so 18 nodes) of c2d-standard-2 for 3 osu metrics
# metrics-16-subset.yaml) for 20x each.
python3 $HERE/random-run.py -p 2.0 -c 3
