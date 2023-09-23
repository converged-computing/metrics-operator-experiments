# Lammps

TODO before runs:
- go through and ensure state of each metric is reset

We need to do a basic benchmark of lammps to demonstrate that the network does not work great.
Our quota will allow for 17 nodes, so we will do experiments on 16 (and add an extra node to install the operator).
We will also use these nodes to run the OSU benchmarks so we have these metrics for the same cluster
and with good bandwidth settings. So for this first test I'm going to bring 
up a size 17 cluster, and only to test LAMMPS in the metrics operator. 
We want to use TIER-1 and a better MTU. This should cost

 - c3-standard-176 is USD 9.19 for 1 node over 1 hour
 - TIER-1 is usually half the cost of the total cluster (at least before)
 
If I take 17 nodes this is ~$170/hour (rounded up)
I'm going to assume ~85/hour for TIER-1 networking (about half)

So for 1 hours, that would be $255, for 3 hours, $765. 
Also note that the c3-standard-176 instance type has:

 - 176 vCPU which is 88 actual cores
 - 704 GB memory

## Experiment Planning

We need to be able to run lammps to demonstrate that it does not perform well with the best Google has to offer in terms of network.
We are using c3 as recommended by the networking team, and in our tests with the Google networking team, we can only get the reasonable problem size (64x16x16) working (albeit poorly) on 8 nodes. 
What I'd like to do is:

- For each of problem sizes 16 (unlikely to work), 8, 4, and 2:
  - Run a large (64x16x16) and small (2x2x2) problem size, three times each
  - On the last (third) run, add hpctoolkit to benchmark, and save data to the host

And then on the same cluster, we will run the OSU Benchmarks, as we previously have.
We will use all recommended libraries / approaches (rocky, intel mpi, and TIER-1 with a high mtu) to demonstrate it's not related to bandwidth, and actually bandwidth does not help us here.

Note that our early experiments were using the Flux Operator, however the HPCToolkit software runs in the metrics operator, and we want to do a fair comparison to compare the same cluster, same way of running lammps, for the actual runs vs. runs that look at performance. 
Note that it's fair to use the Metrics Operator vs the Flux Operator despite using zeromq (Flux) vs not - hpctoolkit won't be measuring the zeromq bootstrap time, but rather will be profiling the lammps binary itself.

### Meeting Notes

Here are notes from our planning meeting.
 
 - Can we compare metrics operator with flux operator to run lammps?
 - Metrics Operator to run lammps (fall back to Flux Operator if does not work)
 - Run lammps on size (16) and size 17 cluster (one node extra for operators) c3-standard-176
   - need to note size 16 likely won't work, it hasn't before. 
   - add tier 1 networking
   - ensure we have maxed out mtu
 - 3x for sizes 16, 8, 4 (fall back to 2x if too long)
 - Metrics Operator to run hpctoolkit (but not going to be measuring the zeromq bootstrap time) only going to be profiling lammps binary
 - Then run OSU Benchmarks - run the same benchmarks here (size 176)

We are measuring bootstrap of communicator but not the bootstrap of MPI, so it wouldn't matter if we are using ssh or zeromq

## Experiments

### Create the Cluster

Let's test a cluster on c3-standard-176 for size 7.
We are following [these best practices](https://cloud.google.com/architecture/best-practices-for-using-mpi-on-compute-engine).

```bash
GOOGLE_PROJECT=myproject
gcloud compute networks create mtu9k --mtu=8896 
gcloud container clusters create test-cluster \
    --threads-per-core=1 \
    --placement-type=COMPACT \
    --num-nodes=17 \
    --region=us-central1-a \
    --project=${GOOGLE_PROJECT} \
    --machine-type=c3-standard-176 \
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

Then install the metrics operator. When we run these experiments we will use a development branch, but when you come back
later this should be merged into main.

```bash
$ kubectl apply -f ./operator/metrics-operator-dev.yaml
```

### 3. LAMMPS with HPCToolkit

We will only run each of these once, and since we need to pull containers / know which sizes don't run,
we will do them first (before the two automated iterations that are expected to complete). For each I will give
a maximum of 10 minutes.

TODO these need to be reversed so largest size pulls containers first! 
Also add time wrapper so we can see how long the entire thing takes to fail.

```bash
# Do these first to pull containers to all nodes
# lammps-small-16
# lammps-large-16
# lammps-small-8
# lammps-large-8
# lammps-large-4
# lammps-small-4
# lammps-large-2
# lammps-small-2
# lammps-large-1
# lammps-small-1

# Start with the one most likely to run
uid=<set uid from above>
outdir="./data/hpctoolkit/${uid}"
mkdir -p ${outdir}
kubectl apply -f ./crd/hpctoolkit/${uid}.yaml
pod=$(kubectl get pods -o json | jq -r .items[0].metadata.name)

# Wait until finished
kubectl logs -c launcher $pod -f
kubectl logs -c launcher $pod > ${outdir}/lammps.log

# If it doesn't run, save database but mark as failed
for pod in $(kubectl get pods -o json | jq -r .items[].metadata.name); do 
    mkdir -p ${outdir}/${pod}-failed
    # kubectl exec -it -c launcher $pod -- /opt/mnt/view/bin/hpcstruct hpctoolkit-result 
    # kubectl exec -it -c launcher $pod -- /opt/mnt/view/bin/hpcprof -o hpctoolkit-result-database hpctoolkit-result 
    kubectl cp -c launcher $pod:/opt/lammps/examples/reaxff/HNS/hpctoolkit-result-database/ $outdir/${pod}-failed/
    kubectl cp -c workers $pod:/opt/lammps/examples/reaxff/HNS/hpctoolkit-result-database/ $outdir/${pod}-failed/
done

# If it works, copy over all hpctoolkit data
for pod in $(kubectl get pods -o json | jq -r .items[].metadata.name); do 
    mkdir -p ${outdir}/$pod; 
    kubectl cp -c launcher $pod:/opt/lammps/examples/reaxff/HNS/hpctoolkit-result-database/ $outdir/$pod/
    kubectl cp -c workers $pod:/opt/lammps/examples/reaxff/HNS/hpctoolkit-result-database/ $outdir/$pod/
done

# Then delete
kubectl delete -f ./crd/hpctoolkit/${uid}.yaml
```

#### 4. LAMMPS Automated

For running lammps at different sizes, we can use the script. Note that we should only run this for sizes we know will complete!

 - large doesn't work for sizes 1,2,4, the problem size is too big for the workers
 - At some point (likely 16) both problem sizes will stop working, and the small problem size times will get worse (cost of connectivity)

```bash
mkdir -p ./data/lammps

# These are known to work from experiment testing run0
time python run-lammps.py --iter 3 --out ./data/lammps --input ./crd/lammps/lammps-small-1.yaml --sleep 5
time python run-lammps.py --iter 3 --out ./data/lammps --input ./crd/lammps/lammps-small-2.yaml --sleep 5
time python run-lammps.py --iter 3 --out ./data/lammps --input ./crd/lammps/lammps-small-4.yaml --sleep 5

# These are unknown
time python run-lammps.py --iter 3 --out ./data/lammps --input ./crd/lammps/lammps-large-8.yaml --sleep 5
time python run-lammps.py --iter 3 --out ./data/lammps --input ./crd/lammps/lammps-small-8.yaml --sleep 5

time python run-lammps.py --iter 3 --out ./data/lammps --input ./crd/lammps/lammps-large-16.yaml --sleep 5
time python run-lammps.py --iter 3 --out ./data/lammps --input ./crd/lammps/lammps-small-16.yaml --sleep 5
```

#### 5. OSU Benchmarks

We now want to run just 3 iterations for each size of the benchmarks.

```bash
mkdir -p ./data/osu-benchmarks
time python run-osu-benchmarks.py --out ./data/osu-benchmarks --input ./crd/osu-benchmarks/metrics-16.yaml --iter 3 --sleep 60
time python run-osu-benchmarks.py --out ./data/osu-benchmarks --input ./crd/osu-benchmarks/metrics-8.yaml --iter 3 --sleep 5
time python run-osu-benchmarks.py --out ./data/osu-benchmarks --input ./crd/osu-benchmarks/metrics-4.yaml --iter 3 --sleep 5
time python run-osu-benchmarks.py --out ./data/osu-benchmarks --input ./crd/osu-benchmarks/metrics-2.yaml --iter 3 --sleep 5
```

#### 6. Clean up

```bash
gcloud container clusters delete test-cluster --region=us-central1-a --quiet
```

And that's it! We've actually used the metrics operator in three ways here:

- Using an application, lammps, as a metric
- Adding an "addon" hpctoolkit to additionally measure that
- Running the OSU Benchmarks too

### Singularity for HPCToolkit

We will need to run this as a post analysis to get the data locally, and across nodes.
We need to copy data from all the nodes

```bash
mkdir -p ./perf
cd ./perf
for pod in $(kubectl get pods -o json | jq -r .items[].metadata.name); do 
    mkdir -p $pod; 
    kubectl cp -c launcher $pod:/opt/lammps/examples/reaxff/HNS/hpctoolkit-lmp-real-measurements/ $pod/
    kubectl cp -c workers $pod:/opt/lammps/examples/reaxff/HNS/hpctoolkit-lmp-real-measurements/ $pod/
done
```

Pull the Singularity container:

```bash
singularity pull docker://ghcr.io/converged-computing/metric-hpctoolkit-viewer:latest
```

Then run (from the directory with your data):

```bash
singularity shell metric-hpctoolkit-viewer_latest.sif 
```

Then use the viewer:

```bash
Singularity> /opt/view/bin/hpcviewer the-professor/
Java version 11
Redirect standard error to /home/vanessa/.hpctoolkit/hpcviewer/x86_64/hpcviewer.err
Singularity> exit
```

