# Lammps Automated

This will only be running automated lammps on a very large cluster size (128).
I am trying to reproduce [run4](../run4) because it was so unexpectedly good I don't believe it.

 - c3-standard-176 is USD 5.08 for 1 node over 1 hour
 - TIER-1 is usually half the cost of the total cluster (at least before)
 
If I take 129 nodes this is ~$ 650.84/hour (rounded up)  and 2 hours would be $1,301.68.
I'm going to assume ~85/hour for TIER-1 networking (about half).

 - 112 vCPU which is 56 actual cores
 - 448 GB memory

Unlike [run3](../run3) we are going to do a larger problem size for this one that we know runs on 16 nodes (and should run on more too).

| Time | Event |
| -----|-------|
| 7:00pm | Bring up cluster |
| 7:55pm | Bring down cluster |

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
    --num-nodes=129 \
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

Then install the metrics operator (I did from a development branch)

```bash
$ make test-deploy-recreate
```

#### 1. LAMMPS Automated

For running lammps at different sizes, we can use the script. Note that the first run is manual (and can be cancelled if needed) and is only intended to pull the containers:

```bash
kubectl apply -f ./crd/lammps/lammps-small-128.yaml
```

I do this either until they are all running (success) or we see enough backoffs that it makes sense to delete and then the next time around will not stress the registry and pull without issue. Note that if you want to save examples for pods as you go, don't forget
to do that at each size:

```bash
kubectl get pods -o json > data/pods-64.json
```

**NOTE** to reproducers - this would be nice to run with 20 iterations each (e.g., `--iter 20` for each) for a more
proper dataset. I just didn't have the credits.

```bash
mkdir -p ./data/lammps

time python run-lammps.py --iter 5 --out ./data/lammps --input ./crd/lammps/lammps-small-128.yaml --sleep 5
time python run-lammps.py --iter 5 --out ./data/lammps --input ./crd/lammps/lammps-small-64.yaml --sleep 5

# Decreased iterations as takes longer to run (staying aware of cost of this cluster)
time python run-lammps.py --iter 4 --out ./data/lammps --input ./crd/lammps/lammps-small-32.yaml --sleep 5
time python run-lammps.py --iter 3 --out ./data/lammps --input ./crd/lammps/lammps-small-16.yaml --sleep 5
time python run-lammps.py --iter 2 --out ./data/lammps --input ./crd/lammps/lammps-small-8.yaml --sleep 5
time python run-lammps.py --iter 1 --out ./data/lammps --input ./crd/lammps/lammps-small-4.yaml --sleep 5
```

#### 6. Clean up

```bash
gcloud container clusters delete test-cluster --region=us-central1-a --quiet
```

And that's it!
 
## Results

### LAMMPS

```bash
mkdir -p ./img/lammps
python plot-lammps.py --results ./data/lammps --out ./img/lammps
```
