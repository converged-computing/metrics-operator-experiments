#!/bin/bash

set -exuo pipefail

HERE=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
GOOGLE_PROJECT=${1}

# This will run the metrics subset for 3 times, each 20 collections
for i in 1 2 3; do
    echo "🥞️ Running top level iteration ${i}"
    time /bin/bash ./collect.sh ${GOOGLE_PROJECT} 18 ./crd/metrics-16-subset.yaml 20
done
