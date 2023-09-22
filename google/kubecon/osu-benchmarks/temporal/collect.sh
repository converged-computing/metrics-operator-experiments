#!/bin/bash

set -exuo pipefail

HERE=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
INSTANCE="c2d-standard-2"
CLUSTER_NAME="osu-cluster"
TIMESTAMP=$(date +"%A_DATE_%Y-%m-%d_TIME_%H-%M-%S")

# User variables
GOOGLE_PROJECT="${1}"
SIZE=${2}
INPUT_FILE=${3}
ITER=${4:-20}

# The metrics.yaml needs to exist
if [[ ! -e "${INPUT_FILE}" ]]; then
    echo "Input metrics yaml file ${INPUT_FILE} does not exist."
fi

echo " Cluster name: ${CLUSTER_NAME}"
echo "   Input file: ${INPUT_FILE}"
echo "Instance type: ${INSTANCE}"
echo "Starting experiment run size ${SIZE} on ${TIMESTAMP} for ${ITER} iterations"

# Add two nodes for jobset and metrics operator
gcloud container clusters create ${CLUSTER_NAME} \
    --threads-per-core=1 \
    --placement-type=COMPACT \
    --zone=us-central1-a \
    --num-nodes=${SIZE} \
    --machine-type=${INSTANCE} \
    --enable-gvnic

# When that is done, we install JobSet
VERSION=v0.2.0

kubectl apply --server-side -f https://github.com/kubernetes-sigs/jobset/releases/download/$VERSION/manifests.yaml
sleep 10

# Now install the metrics operator. Here we keep the exact version and digest.
# Test development version
kubectl apply -f $HERE/operator/metrics-operator-dev.yaml 
#kubectl apply -f $HERE/operator/metrics-operator.yaml
sleep 10

# Save some metadata about the nodes
# This is the output time
outdir="${HERE}/data/${TIMESTAMP}"
mkdir -p ${outdir}
kubectl get nodes -o json > ${outdir}/nodes-${SIZE}.json

# Run the experiment for that many iterations
python run-experiment.py --out ${outdir} --input ${INPUT_FILE} --iter ${ITER} --sleep 60
gcloud container clusters delete --quiet --zone=us-central1-a ${CLUSTER_NAME}
