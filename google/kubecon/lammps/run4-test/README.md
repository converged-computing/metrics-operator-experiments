# Lammps Automated (test)

This will test running a larger problem size of LAMMPS on a smaller (9 node) cluster. This
is to ensure when we bring the larger cluster up, we at least knows it runs on size 8.

 - c3-standard-176 is USD 5.08 for 1 node over 1 hour
 - TIER-1 is usually half the cost of the total cluster (at least before)
 
This should be ~$45/hour, which isn't bad for testing.

 - 112 vCPU which is 56 actual cores
 - 448 GB memory

Unlike [run3](../run3) we are going to do a larger problem size for this one that we know runs on 16 nodes (and should run on more too).

## Experiments

### Create the Cluster

Let's test a cluster on c3-standard-176 for size 17.
We are following [these best practices](https://cloud.google.com/architecture/best-practices-for-using-mpi-on-compute-engine).

```bash
GOOGLE_PROJECT=myproject
gcloud compute networks create mtu9k --mtu=8896 
gcloud container clusters create test-cluster \
    --threads-per-core=1 \
    --placement-type=COMPACT \
    --num-nodes=9 \
    --region=us-central1-a \
    --project=${GOOGLE_PROJECT} \
    --machine-type=c2d-standard-112 \
    --network-performance-configs=total-egress-bandwidth-tier=TIER_1 \
    --enable-gvnic \
    --network=mtu9k \
    --system-config-from-file=./crd/system-config.yaml
```

And save metadata about the nodes.

```bash
mkdir -p ./data
kubectl get nodes -o json > data/nodes.json
```

Install the Metrics Operator SDK. Version 19 has added support for custom (raw) log parsing.

```bash
pip install metricsoperator==0.0.19
```

### 2. Setup the Metrics Operator

Install JobSet first:

```bash
VERSION=v0.2.0
kubectl apply --server-side -f https://github.com/kubernetes-sigs/jobset/releases/download/$VERSION/manifests.yaml
```

Then install the metrics operator. 

```bash
$ kubectl apply -f ./operator/metrics-operator.yaml
```

#### 1. LAMMPS Automated

For running lammps at different sizes, we can use the script. I am only running a problem size 2x2x2 that
I know will run at the smaller sizes and complete, the idea being that we want to see how large this
can go before it stops working.


```bash
mkdir -p ./data/lammps

# Note this takes about 1:22 to 1:23
time python run-lammps.py --iter 3 --out ./data/lammps --input ./crd/lammps/lammps-small-8.yaml --sleep 5   5 seconds each 

# size 8 is 1:23
# size 4 is 2:31
# size 2 is 4:43
# size 1 is 9:05
```

We can use these times to estimate runs for tomorrow.

#### 6. Clean up

```bash
gcloud container clusters delete test-cluster --region=us-central1-a --quiet
```

