# Single Run Experiment on GKE

We are going to combine all CRDs into a test experiment here, and prototype running apps in a loop, and saving results. This is the CPU variant of the experiment.

- Start time: 17:40
- End time: 

We will want to estimate cost from this. The experiment will proceed as follows:

```console
For each experiment (crd in ./crd):
  Create the MiniCluster, and shell in
  Connect to the flux broker, loading spack env if needed
  Create output directory for logs
  For each size of experiment to run (with custom params)?
    For iterations 1..N (likely 1 for now)
      Run the experiment, save to log

  Compress results with oras
  Push to OCI registry for results
```

## Notes

TODO price estimates.


## Experiment

### 1. Setup

Bring up the cluster (with some number of nodes) and install the drivers. Have your GitHub packages (or other registry credential / token) ready. This does not work.


```bash
GOOGLE_PROJECT=myproject

gcloud compute networks create mtu9k --mtu=8896 
time gcloud container clusters create test-cluster \
    --threads-per-core=1 \
    --num-nodes=32 \
    --machine-type=c2d-standard-112 \
    --network-performance-configs=total-egress-bandwidth-tier=TIER_1 \
    --enable-gvnic \
    --network=mtu9k \
    --placement-type=COMPACT \
    --system-config-from-file=./system-config.yaml \
    --region=us-central1-a \
    --project=${GOOGLE_PROJECT} 
```

5m 29 seconds. Install the Flux Operator:

```bash
kubectl apply -f https://raw.githubusercontent.com/flux-framework/flux-operator/main/examples/dist/flux-operator.yaml
```

Now we are ready for different MiniCluster setups. For each of the below, to shell in to the lead broker (index 0) you do:

```bash
kubectl exec -it flux-sample-0-xxx bash
```

Note that the configs are currently set to 8 nodes, with 8 gpu each. size 32vcpu (16 cores) instance (n1-standard-32).

### 2. Applications

#### AMG2023

Create the minicluster and shell in. Note this first pull takes the longest (about ~5 minutes)

```bash
kubectl apply -f ./crd/amg2023.yaml
time kubectl wait --for=condition=ready pod -l job-name=flux-sample --timeout=600s
```

This one requires sourcing spack

```bash
. /etc/profile.d/z10_spack_environment.sh
flux proxy local:///mnt/flux/view/run/flux/local bash
```

Here is an example loop through sizes and iterations. Note that this is done expecting that parameters
might change for different sizes.

```console
oras login ghcr.io --username vsoch
app=amg2023
output=./results/$app

mkdir -p $output
for i in $(seq 1 1); do     
  echo "Running iteration $i"
  # didn't run
  time flux run -N 32 -n 1792 amg -P 64 7 4 -n 64 64 128 |& tee ./$output/$app-$size-iter-${i}.out

  # 34 seconds
  time flux run -N 16 -n 896 amg -P 32 7 4 -n 64 64 128 |& tee ./$output/$app-$size-iter-${i}.out

  # 25 seconds
  time flux run -N 8 -n 448 amg -P 16 7 4 -n 64 64 128  |& tee ./$output/$app-$size-iter-${i}.out

  # 20 seconds
  time flux run -N 4 -n 224 amg -P 8 7 4 -n 64 64 128  |& tee ./$output/$app-$size-iter-${i}.out
done

oras push ghcr.io/converged-computing/metrics-operator-experiments/performance:test-$app $output
```

On two nodes this problem is almost instant.

```bash
kubectl delete -f ./crd/amg2023.yaml
```

#### Kripke

```bash
kubectl apply -f ./crd/kripke.yaml
time kubectl wait --for=condition=ready pod -l job-name=flux-sample --timeout=600s
```

About 46 seconds extra pull time.

```bash
flux proxy local:///mnt/flux/view/run/flux/local bash
```

```console
oras login ghcr.io --username vsoch
app=kripke
output=./results/$app

mkdir -p $output
for i in $(seq 1 1); do     
  echo "Running iteration $i"
done

oras push ghcr.io/converged-computing/metrics-operator-experiments/performance:test-$app $output
```

```bash
kubectl delete -f ./crd/kripke.yaml
```

#### Laghos

```bash
kubectl apply -f ./crd/laghos.yaml
time kubectl wait --for=condition=ready pod -l job-name=flux-sample --timeout=600s
```

```bash
flux proxy local:///mnt/flux/view/run/flux/local bash
```

```console
oras login ghcr.io --username vsoch
app=laghos
output=./results/$app

mkdir -p $output
for i in $(seq 1 1); do     
  echo "Running iteration $i"
  time flux run -N16 -n 896 /opt/laghos/laghos -p 1 -m ./data/cube01_hex.mesh -rs 2 -tf 0.6 -pa -cfl 0.08 --max-steps 20 |& tee ./$output/$app-$size-iter-${i}.out

  # 26 seconds
  time flux run -N8 -n 448 /opt/laghos/laghos -p 1 -m ./data/box01_hex.mesh -rs 2 -tf 0.6 -pa -cfl 0.08 --max-steps 20

  # 18 seconds
  time flux run -N4 -n 224 /opt/laghos/laghos -p 1 -m ./data/box01_hex.mesh -rs 2 -tf 0.6 -pa -cfl 0.08 --max-steps 20

  # 7 seconds
  time flux run -N2 -n 112 /opt/laghos/laghos -p 1 -m ./data/box01_hex.mesh -rs 2 -tf 0.6 -pa -cfl 0.08 --max-steps 20
done

oras push ghcr.io/converged-computing/metrics-operator-experiments/performance:test-$app $output
```

```bash
kubectl delete -f ./crd/laghos.yaml
```


#### LAMMPS

```bash
kubectl apply -f ./crd/lammps.yaml
time kubectl wait --for=condition=ready pod -l job-name=flux-sample --timeout=600s
```

```bash
flux proxy local:///mnt/flux/view/run/flux/local bash
```

```console
oras login ghcr.io --username vsoch
app=lammps
output=./results/$app

# 1 minute 1 second on 2 nodes
mkdir -p $output
for i in $(seq 1 2); do     
  echo "Running iteration $i"
  flux run -N2  -n 8 lmp -k on g 4 -sf kk -pk kokkos newton on neigh half -in in.snap.test -var snapdir 2J8_W.SNAP -v x 228 -v y 228 -v z 228 -var nsteps 20000  |& tee ./$output/$app-$size-iter-${i}.out
done

oras push ghcr.io/converged-computing/metrics-operator-experiments/performance:test-$app $output
```

```bash
kubectl delete -f ./crd/lammps.yaml
```

#### Magma

> With or without mnist data?

```bash
kubectl apply -f ./crd/magma.yaml
time kubectl wait --for=condition=ready pod -l job-name=flux-sample --timeout=600s
```

```bash
flux proxy local:///mnt/flux/view/run/flux/local bash
```

```console
oras login ghcr.io --username vsoch
app=magma
output=./results/$app

mkdir -p $output
for i in $(seq 1 2); do     
  echo "Running iteration $i"
  flux run -N2 -n 8 -o gpu-affinity=per-task /opt/magma/magma-2.8.0/build/testing/testing_dgemm |& tee ./$output/$app-$size-iter-${i}.out
done

oras push ghcr.io/converged-computing/metrics-operator-experiments/performance:test-$app $output
```

Other commands

```bash
flux run -N2 -n 8 -o gpu-affinity=per-task /opt/magma/magma-2.8.0/build/testing/testing_dgemm
time flux run -N1 -n 4 -o gpu-affinity=per-task /opt/magma/magma-2.8.0/build/testing/testing_dgemm --ngpu 1

# Note this seemed to allow running across gpu (the --gpus 4 worked) but in practice we didn't see them running.
# export MAGMA_NUM_GPUS=4
time flux run -N2 -n 8 -o gpu-affinity=per-task /opt/magma/magma-2.8.0/build/testing/testing_dgemm_vbatched --ngpu 1
```
```console
using MAGMA GPU interface
magma_zgesv failed with info=    1
magma_zgesv failed with info=    1
using MAGMA GPU interface
```

```bash
kubectl delete -f ./crd/magma.yaml
```

#### MiniFE


```bash
kubectl apply -f ./crd/minife.yaml
time kubectl wait --for=condition=ready pod -l job-name=flux-sample --timeout=600s
```

```bash
flux proxy local:///mnt/flux/view/run/flux/local bash
```

```console
oras login ghcr.io --username vsoch
app=minife
output=./results/$app

# 5.7 seconds
mkdir -p $output
for i in $(seq 1 2); do     
  echo "Running iteration $i"
  flux run -N2 -n 8 -o gpu-affinity=per-task miniFE.x nx=620 ny=620 nz=620 num_devices=4 use_locking=1 elem_group_size=2 use_elem_mat_fields=10 verify_solution=0 |& tee ./$output/$app-$size-iter-${i}.out
done

oras push ghcr.io/converged-computing/metrics-operator-experiments/performance:test-$app $output
```

```bash
kubectl delete -f ./crd/minife.yaml
```

#### Mixbench

```bash
kubectl apply -f ./crd/mixbench.yaml
time kubectl wait --for=condition=ready pod -l job-name=flux-sample --timeout=600s
```

```bash
flux proxy local:///mnt/flux/view/run/flux/local bash
```

```console
oras login ghcr.io --username vsoch
app=mixbench
output=./results/$app

# ~26 seconds
mkdir -p $output
for i in $(seq 1 2); do     
  echo "Running iteration $i"
  flux run -N2 -n 8 ./wrapper 64 |& tee ./$output/$app-$size-iter-${i}.out
done

oras push ghcr.io/converged-computing/metrics-operator-experiments/performance:test-$app $output
```

```bash
kubectl delete -f ./crd/mixbench.yaml
```


#### Mt Gem


```bash
kubectl apply -f ./crd/mt-gem.yaml
time kubectl wait --for=condition=ready pod -l job-name=flux-sample --timeout=600s
```

```bash
flux proxy local:///mnt/flux/view/run/flux/local bash
```

```console
oras login ghcr.io --username vsoch
app=mt-gem
output=./results/$app

mkdir -p $output
for i in $(seq 1 2); do     
  echo "Running iteration $i"
  flux run -N2 -n 8 /opt/gem/mt-dgemm.x 8192 200 |& tee ./$output/$app-$size-iter-${i}.out
done

oras push ghcr.io/converged-computing/metrics-operator-experiments/performance:test-$app $output
```

```bash
kubectl delete -f ./crd/mt-gem.yaml
```


#### Multi GPU Models

```bash
kubectl apply -f ./crd/multi-gpu-models.yaml
time kubectl wait --for=condition=ready pod -l job-name=flux-sample --timeout=600s
```

```bash
flux proxy local:///mnt/flux/view/run/flux/local bash
```

```console
oras login ghcr.io --username vsoch
app=multi-gpu-models
output=./results/$app

mkdir -p $output
for i in $(seq 1 2); do     
  echo "Running iteration $i"
  flux run -N1 --gpus-per-node 4 /opt/multi-gpu-programming-models/mpi/jacobi -niter 20000 |& tee ./$output/$app-$size-iter-${i}.out
done

oras push ghcr.io/converged-computing/metrics-operator-experiments/performance:test-$app $output
```

Other options:

```bash
# This was 30 seconds, and took up about 100% of each of 4 gpu
flux submit --watch -N1 --gpus-per-node 4 /opt/multi-gpu-programming-models/mpi/jacobi -niter 5000

# 48 seconds
flux submit --watch -N1 --gpus-per-node 4 /opt/multi-gpu-programming-models/mpi/jacobi -niter 10000

# 1 minute 30 seconds
flux submit --watch -N1 --gpus-per-node 4 /opt/multi-gpu-programming-models/mpi/jacobi -niter 20000

# 28 seconds
flux run -N2 -n 8 /opt/multi-gpu-programming-models/mpi/jacobi -niter 5000

# 50 seconds
flux run -N2 -n 8 /opt/multi-gpu-programming-models/mpi/jacobi -niter 10000

# 1 minute 36 seconds
flux run -N2 -n 8 /opt/multi-gpu-programming-models/mpi/jacobi -niter 10000
```


```bash
kubectl delete -f ./crd/multi-gpu-models.yaml
```

#### Nek5000

```bash
kubectl apply -f ./crd/nek5000.yaml
time kubectl wait --for=condition=ready pod -l job-name=flux-sample --timeout=600s
```

```bash
flux proxy local:///mnt/flux/view/run/flux/local bash
```

```console
oras login ghcr.io --username vsoch
app=nek5000
output=./results/$app

mkdir -p $output
for i in $(seq 1 2); do     
  echo "Running iteration $i"
  flux run -N2 -n 8 nekrs --setup turbPipe.par |& tee ./$output/$app-$size-iter-${i}.out
done

oras push ghcr.io/converged-computing/metrics-operator-experiments/performance:test-$app $output
```

Other commands:

```bash
# Local test
cd /opt/nekrs/examples/turbPipePeriodic

# this uses about 80% of each of 2
mpirun --allow-run-as-root -np 2 nekrs --setup turbPipe.par

# this uses about 68-74% of each of 4
mpirun --allow-run-as-root -np 4 nekrs --setup turbPipe.par

# 4 GPU does not converge
mpirun --allow-run-as-root -n 4 nekrs --setup turbPipe.par

# Flux with one node and two nodes
flux run -N1 -n 4 nekrs --setup turbPipe.par
flux run -N2 -n 8 nekrs --setup turbPipe.par
```

```bash
kubectl delete -f ./crd/nek5000.yaml
```


#### OSU

```bash
kubectl apply -f ./crd/osu.yaml
time kubectl wait --for=condition=ready pod -l job-name=flux-sample --timeout=600s
```

```bash
flux proxy local:///mnt/flux/view/run/flux/local bash
```

```console
oras login ghcr.io --username vsoch
app=osu
output=./results/$app

mkdir -p $output
for i in $(seq 1 2); do     
  echo "Running iteration $i"
  flux run -N2 -n2 /opt/osu-benchmark/build.openmpi/mpi/pt2pt/osu_bw -d cuda D D |& tee ./$output/$app-osu_bw-$size-iter-${i}.out
  flux run -N2 -n8 -o gpu-affinity=per-task /opt/osu-benchmark/build.openmpi/mpi/collective/osu_allreduce -d cuda D D |& tee ./$output/$app-osu_allreduce-$size-iter-${i}.out
  flux run -N2 -n2 -o gpu-affinity=per-task /opt/osu-benchmark/build.openmpi/mpi/pt2pt/osu_latency -d cuda D D |& tee ./$output/$app-osu_latency-$size-iter-${i}.out
done

oras push ghcr.io/converged-computing/metrics-operator-experiments/performance:test-$app $output
```

```bash
kubectl delete -f ./crd/osu.yaml
```

#### Quicksilver

```bash
kubectl apply -f ./crd/quicksilver.yaml
time kubectl wait --for=condition=ready pod -l job-name=flux-sample --timeout=600s
```

```bash
flux proxy local:///mnt/flux/view/run/flux/local bash
```

```console
oras login ghcr.io --username vsoch
app=quicksilver
output=./results/$app

mkdir -p $output
for i in $(seq 1 2); do     
  echo "Running iteration $i"
  flux run -N2 -n 8 qs --inputFile /opt/quicksilver/Examples/CORAL2_Benchmark/Problem1/Coral2_P1.inp  |& tee ./$output/$app-$size-iter-${i}.out
done

oras push ghcr.io/converged-computing/metrics-operator-experiments/performance:test-$app $output
```

Both options:

```bash
flux run -N2 -n 8 qs --inputFile /opt/quicksilver/Examples/CORAL2_Benchmark/Problem1/Coral2_P1.inp

# Coral 2 example
flux run -N2 -n 8 qs --inputFile /opt/quicksilver/Examples/CORAL2_Benchmark/Problem2/Coral2_P2.inp
```

```bash
kubectl delete -f ./crd/quicksilver.yaml
```

#### Linpack

**not tested**

```bash
kubectl apply -f ./crd/linpack.yaml
time kubectl wait --for=condition=ready pod -l job-name=flux-sample --timeout=600s
```
About 30 seconds extra pull time.

```bash
flux proxy local:///mnt/flux/view/run/flux/local bash
```

```console
oras login ghcr.io --username vsoch
app=linpack
output=./results/$app

mkdir -p $output
for i in $(seq 1 1); do     
  echo "Running iteration $i"

  # This still runs on each node, needs to be recompiled
  time flux run -N 4 -n 384 -o cpu-affinity=per-task TODOADDCOMMAND |& tee ./$output/$app-$size-iter-${i}.out

  # This still runs on each node, needs to be recompiled
  time flux run -N 2 -n 192 -o cpu-affinity=per-task TODOADDCOMMAND |& tee ./$output/$app-$size-iter-${i}.out

done

oras push ghcr.io/converged-computing/metrics-operator-experiments/performance:test-aws-$app $output
```

```bash
kubectl delete -f ./crd/linpack.yaml
```


#### Stream

```bash
kubectl apply -f ./crd/stream.yaml
time kubectl wait --for=condition=ready pod -l job-name=flux-sample --timeout=600s
```

```bash
flux proxy local:///mnt/flux/view/run/flux/local bash
```

```console
oras login ghcr.io --username vsoch
app=stream
output=./results/$app

mkdir -p $output
for i in $(seq 1 2); do     
  echo "Running iteration $i"  
  flux run -N2 -n 8 -o gpu-affinity=per-task stream  |& tee ./$output/$app-$size-iter-${i}.out
done

oras push ghcr.io/converged-computing/metrics-operator-experiments/performance:test-$app $output
```

```bash
kubectl delete -f ./crd/stream.yaml
```

### Clean Up

When you are done:

```bash
gcloud container clusters delete test-cluster --region=us-central1-a
```
