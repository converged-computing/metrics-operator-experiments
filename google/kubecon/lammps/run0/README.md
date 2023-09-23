# Lammps (Test)

> This is a test run preparing for the larger runs. I'm choosing a smaller cluster for cost, etc.

For full experiment details, see [run1](run1). This is a testing run for that.

 - c3-standard-176 is USD 9.19 for 1 node over 1 hour
 - TIER-1 is usually half the cost of the total cluster (at least before)
 
If I take 5 nodes this is ~$50/hour (rounded up)
I'm going to assume ~25/hour for TIER-1 networking (about half)

So for 1 hours, that would be $75 
Also note that the c3-standard-176 instance type has:

 - 176 vCPU which is 88 actual cores
 - 704 GB memory

## Experiments

### Create the Cluster

Let's test a cluster on c3-standard-176 for size 5.
We are following [these best practices](https://cloud.google.com/architecture/best-practices-for-using-mpi-on-compute-engine).

```bash
GOOGLE_PROJECT=myproject
gcloud compute networks create mtu9k --mtu=8896
gcloud container clusters create test-cluster \
    --threads-per-core=1 \
    --placement-type=COMPACT \
    --num-nodes=5 \
    --project=${GOOGLE_PROJECT} \
    --region=us-central1-a \
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

```bash
# Do for each of:
# lammps-large-1  # NO OUTPUT for 5 minutes, not going to run, problem size too big for one node
# lammps-small-1  WORKED
# lammps-large-2  # NO OUTPUT (after "Time step: 0.1" for a long time) and job terminated on failure, we have the full log for this one.
# lammps-small-2  WORKED
# lammps-large-4  # DITTO - killed
# lammps-small-4  WORKED

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

Notes from lammps-large-1 (I didn't save this log, but it looks like the others where it was killed)

```console
===================================================================================
=   BAD TERMINATION OF ONE OF YOUR APPLICATION PROCESSES
=   RANK 87 PID 157 RUNNING AT metricset-sample-l-0-0.ms.default.svc.cluster.local
=   KILLED BY SIGNAL: 9 (Killed)
===================================================================================
```

#### 4. LAMMPS Automated

For running lammps at different sizes, we can use the script. Note that we should only run this for sizes we know will complete!

```bash
time python run-lammps.py --iter 1 --out ./data --input ./crd/lammps/lammps-small-1.yaml
time python run-lammps.py --iter 1 --out ./data --input ./crd/lammps/lammps-small-2.yaml
time python run-lammps.py --iter 1 --out ./data --input ./crd/lammps/lammps-small-4.yaml
```

#### 5. OSU Benchmarks

We now want to run just 3 iterations for each size of the benchmarks.

```bash
mkdir -p ./data/osu-benchmarks
time python run-osu-benchmarks.py --out ./data/osu-benchmarks --input ./crd/osu-benchmarks/metrics-4.yaml --iter 5 --sleep 60
NOT RUN YET time python run-osu-benchmarks.py --out ./data/osu-benchmarks --input ./crd/osu-benchmarks/metrics-2.yaml --iter 5 --sleep 5
```

And that's it! We've actually used the metrics operator in three ways here:

- Using an application, lammps, as a metric
- Adding an "addon" hpctoolkit to additionally measure that
- Running the OSU Benchmarks too

#### 6. Clean up

```bash
gcloud container clusters delete test-cluster --region=us-central1-a --quiet
```

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

