# OSU Experiments

These are the official CRD experiments (we are ready!) We will generate data first,
save all metadata and logs, and then parse them after. Each YAML in [crd](crd) 
represents a subset of experiments to run. Since networking
might be influenced by having more than one job on the cluster, we run them each once
at a time.

## OSU Benchmarks

Note that we will be using this configuration (130 nodes) is ~$12/hour (rounded up)

```bash
GOOGLE_PROJECT=myproject

# Add two nodes for jobset and metrics operator
gcloud container clusters create osu-cluster \
    --threads-per-core=1 \
    --placement-type=COMPACT \
    --num-nodes=130 \
    --machine-type=c2d-standard-2 \
    --enable-gvnic
```

Install JobSet

```bash
VERSION=v0.2.0
kubectl apply --server-side -f https://github.com/kubernetes-sigs/jobset/releases/download/$VERSION/manifests.yaml
```

Install the metrics operator. Here we keep the exact version and digest.

```bash
kubectl apply -f ./operator/metrics-operator.yaml
```

Save some metadata about the nodes:

```bash
mkdir -p ./results
kubectl get nodes -o json > results/nodes-128.json
```

Install the Metrics Operator SDK. Version 19 has added support for custom (raw) log parsing.

```bash
pip install metricsoperator==0.0.19
# or with plotting libraries for later
pip install -r requirements.txt
```

### Experiments

The following experiments will be run! It's useful to do a test first to sanity check output, etc.

#### Test Run

```bash
python run-experiment.py --out ./data --input ./crd/test/metrics-4.yaml --iter 2 --sleep 60
```

#### Actual Runs

Now we can automate many different runs with the script. Note that we target a directory of CRD, so you can target each combination
of size and iterations (which varies).

```bash
# Run the test experiments - pull to all 128 pods first
# Size 128 we don't attempt the size 1 runs (too long)
python run-experiment.py --out ./data --input ./crd/metrics-20x-128.yaml --iter 20 --sleep 60
python run-experiment.py --out ./data --input ./crd/metrics-20x-128-large.yaml --iter 20 --sleep 60

# Size 64 we split into 20x and 1x for larger runs
python run-experiment.py --out ./data --input ./crd/metrics-20x-64.yaml --iter 20 --sleep 5

# Note that I originally did 1x here for larger, but they were quick, so I added 19 more (total of 20)
python run-experiment.py --out ./data --input ./crd/metrics-1x-64.yaml --iter 1 --sleep 5
python run-experiment.py --out ./data --input ./crd/metrics-19x-64.yaml --iter 19 --sleep 5

# Size 32 is the same... these could have been combined into one but I didn't realize they were faster either
# Size 16 on we can just run one file!
python run-experiment.py --out ./data --input ./crd/metrics-20x-32.yaml --iter 20 --sleep 5
python run-experiment.py --out ./data --input ./crd/metrics-20x-32-large.yaml --iter 20 --sleep 5
python run-experiment.py --out ./data --input ./crd/metrics-20x-16.yaml --iter 20 --sleep 5
python run-experiment.py --out ./data --input ./crd/metrics-20x-8.yaml --iter 20 --sleep 5
python run-experiment.py --out ./data --input ./crd/metrics-20x-4.yaml --iter 20 --sleep 5
```

When you are done, clean up!

```bash
gcloud container clusters delete osu-cluster
```

Note for the above I did last minute adjustments to ultimately run more iterations.
For some reason this cluster did not have the slowness of the first one. E.g.,
a run that took 4 hours was done

### Results

We have a script to parse results into data frames and images.

```bash
python plot-times.py --results ./data --out ./img
```

#### Wrapped Times

Since we had incredibly slow times the first time around, I decided to do the same here (and make plots for that).
We didn't see any weirdness this time - as expected, for each metric the time to run it increased with increasing size.
These plots are the real times, in seconds, across sizes.
I'm including an example comparison between the testing run and this one - it's alarming (4+ hours difference)

<details>

<summary>Alarming difference between two different 64 clusters</summary>

```console
time mpirun --hostfile ./hostlist.txt --allow-run-as-root -np 64 -map-by ppr:1:node -rank-by core /opt/osu-benchmark/build.openmpi/libexec/osu-micro-benchmarks/mpi/collective/osu_allgather

# OSU MPI Allgather Latency Test v5.8
# Size       Avg Latency(us)
1                  256153.75
2                  256419.24
4                  255733.85
8                  257292.16
16                 256089.31
32                 256481.62
64                 255988.02
128                257387.12
256                256602.52
512                257588.14
1024              1308098.70
2048              1306422.61
4096              1311518.21
8192              1311357.26
16384             1315375.37
32768             3600736.73
65536             3715001.02
131072            3720411.73
262144            3792049.28
524288            3951282.13
1048576           5553244.52

real	261m44.303s
user	36m49.467s
sys	219m10.878s

```

osu_allgather on 64 nodes for this run (even faster) (formatted into json with the better automation this time)

```console
            "time mpirun --hostfile ./hostlist.txt --allow-run-as-root -np 64 -map-by ppr:1:node -rank-by core /opt/osu-benchmark/
build.openmpi/libexec/osu-micro-benchmarks/mpi/collective/osu_allgather",
            "# OSU MPI Allgather Latency Test v5.8",
            "# Size       Avg Latency(us)",
            "1                     726.78",
            "2                     883.14",
            "4                     738.37",
            "8                     834.10",
            "16                    741.27",
            "32                    991.50",
            "64                    998.09",
            "128                   962.28",
            "256                   895.28",
            "512                   946.23",
            "1024                 4130.64",
            "2048                 4279.99",
            "4096                 4376.05",
            "8192                 5513.11",
            "16384                6569.73",
            "32768               20212.10",
            "65536               25610.89",
            "131072              30649.87",
            "262144              46786.95",
            "524288              81370.22",
            "1048576            147033.37",
            "real\t1m39.490s",
            "user\t0m12.951s",
            "sys\t1m23.471s",
```

You can see the first (the testing cluster) was over 4 hours, and the second was under 2 minutes. I don't know how to explain
this.

</details>

[](img/osu_acc_latency-times-seconds-hist-4-to-128.png)
[](img/osu_allgather-times-seconds-hist-4-to-128.png)
[](img/osu_allreduce-times-seconds-hist-4-to-128.png)
[](img/osu_barrier-times-seconds-hist-4-to-128.png)
[](img/osu_bibw-times-seconds-hist-4-to-128.png)
[](img/osu_bw-times-seconds-hist-4-to-128.png)
[](img/osu_cas_latency-times-seconds-hist-4-to-128.png)
[](img/osu_fop_latency-times-seconds-hist-4-to-128.png)
[](img/osu_get_acc_latency-times-seconds-hist-4-to-128.png)
[](img/osu_get_bw-times-seconds-hist-4-to-128.png)
[](img/osu_get_latency-times-seconds-hist-4-to-128.png)
[](img/osu_hello-times-seconds-hist-4-to-128.png)
[](img/osu_ibarrier-times-seconds-hist-4-to-128.png)
[](img/osu_init-times-seconds-hist-4-to-128.png)
[](img/osu_latency_mp-times-seconds-hist-4-to-128.png)
[](img/osu_latency_mt-times-seconds-hist-4-to-128.png)
[](img/osu_latency-times-seconds-hist-4-to-128.png)
[](img/osu_mbw_mr-times-seconds-hist-4-to-128.png)
[](img/osu_multi_lat-times-seconds-hist-4-to-128.png)
[](img/osu_put_bibw-times-seconds-hist-4-to-128.png)
[](img/osu_put_bw-times-seconds-hist-4-to-128.png)
[](img/osu_put_latency-times-seconds-hist-4-to-128.png)


#### Paired or One-Sided (two nodes)

These are only using two nodes, regardless of the size of the cluster. Thus, we would expect
times to be the same, and we largely do see that.

[](img/osu_acc_latency-box-4-to-128.png)
[](img/osu_acc_latency-line-4-to-128.png)
[](img/osu_bibw-box-4-to-128.png)
[](img/osu_bibw-line-4-to-128.png)
[](img/osu_bw-box-4-to-128.png)
[](img/osu_bw-line-4-to-128.png)
[](img/osu_cas_latency-box-4-to-128.png)
[](img/osu_cas_latency-line-4-to-128.png)
[](img/osu_fop_latency-box-4-to-128.png)
[](img/osu_fop_latency-line-4-to-128.png)
[](img/osu_get_acc_latency-box-4-to-128.png)
[](img/osu_get_acc_latency-line-4-to-128.png)
[](img/osu_get_bw-box-4-to-128.png)
[](img/osu_get_bw-line-4-to-128.png)
[](img/osu_get_latency-box-4-to-128.png)
[](img/osu_get_latency-line-4-to-128.png)
[](img/osu_latency-box-4-to-128.png)
[](img/osu_latency-line-4-to-128.png)
[](img/osu_latency_mp-box-4-to-128.png)
[](img/osu_latency_mp-line-4-to-128.png)
[](img/osu_latency_mt-box-4-to-128.png)
[](img/osu_latency_mt-line-4-to-128.png)
[](img/osu_put_bibw-box-4-to-128.png)
[](img/osu_put_bibw-line-4-to-128.png)
[](img/osu_put_bw-box-4-to-128.png)
[](img/osu_put_bw-line-4-to-128.png)
[](img/osu_put_latency-box-4-to-128.png)
[](img/osu_put_latency-line-4-to-128.png)

#### Collective (or >2 nodes)

These we might see an influence of scale.

[](img/osu_allreduce-box-4-to-128.png)
[](img/osu_allreduce-line-4-to-128.png)
[](img/osu_allgather-box-4-to-128.png)
[](img/osu_allgather-line-4-to-128.png)

[](img/osu_init-hist-4-to-128.png)
[](img/osu_ibarrier-compute(us)-hist-4-to-128.png)
[](img/osu_ibarrier-overall(us)-hist-4-to-128.png)
[](img/osu_ibarrier-overlap(%)-hist-4-to-128.png)
[](img/osu_ibarrier-pure-comm-(us)-hist-4-to-128.png)
[](img/osu_barrier-hist-4-to-128.png)
[](img/osu_mbw_mr-mb-s-hist-4-to-128.png)
[](img/osu_mbw_mr-messages-s-hist-4-to-128.png)
[](img/osu_multi_lat-box-4-to-128.png)
[](img/osu_multi_lat-line-4-to-128.png)
