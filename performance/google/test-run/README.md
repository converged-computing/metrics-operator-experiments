# Single Run Experiment on GKE

We are going to combine all CRDs into a test experiment here, and prototype running apps in a loop, and saving results.

- Start time: 5:02pm Mountain, 5:54pm
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

We previously were asking for 8 across two nodes, now we are going to ask for 8 per node. We won't have time to look at GPU usage and tweak, we just have time to ensure the apps run and generate output we can save. If we do 8 GPU for 8 nodes, this would be 64 x [the cost per hour](https://cloud.google.com/compute/gpus-pricing) $2.48, which is $158/hour. We can adjust from that size depending on our risk tolerance. If we go the full size, 32 nodes * 8 GPU, that would be $634.88 per hour. We'd only get one hour, if we were safe, because we only have 1K in credits left.

## Experiment

### 1. Setup

Bring up the cluster (with some number of nodes) and install the drivers. Have your GitHub packages (or other registry credential / token) ready. This does not work.

```bash
GOOGLE_PROJECT=myproject
NODES=4
GPUS=4

gcloud compute networks create mtu9k --mtu=8896 

time gcloud container clusters create gpu-two-cluster \
    --threads-per-core=1 \
    --accelerator type=nvidia-tesla-v100,count=$GPUS \
    --num-nodes=$NODES \
    --machine-type=n1-standard-32 \
    --network-performance-configs=total-egress-bandwidth-tier=TIER_1 \
    --enable-gvnic \
    --network=mtu9k \
    --system-config-from-file=./system-config.yaml \
    --region=us-central1-a \
    --project=${GOOGLE_PROJECT} 
```

- Up time: 5:54


```console
NODES=16
GPUS=8

time gcloud container clusters create gpu-cluster \
    --threads-per-core=1 \
    --accelerator type=nvidia-tesla-v100,count=$GPUS \
    --num-nodes=$NODES \
    --machine-type=n1-standard-32 \
    --region=us-central1-a \
    --project=${GOOGLE_PROJECT} 
```

- Creation times:
  - Cluster: 6 min 13 seconds

Install the daemonset:

```bash
kubectl apply -f daemonset.yaml
```

Sanity check installed on all nodes

```bash
kubectl get nodes -o json | jq .items[].status.allocatable
kubectl get nodes -o json | jq .items[].status.allocatable | grep nvidia | wc -l
```

Install the Flux Operator:

```bash
kubectl apply -f https://raw.githubusercontent.com/flux-framework/flux-operator/main/examples/dist/flux-operator.yaml
```

Now we are ready for different MiniCluster setups. For each of the below, to shell in to the lead broker (index 0) you do:

```bash
kubectl exec -it flux-sample-0-xxx bash
```

Note that the configs are currently set to 8 nodes, with 8 gpu each. size 32vcpu (16 cores) instance (n1-standard-32).

### 2. AMG2023

Create the minicluster and shell in. Note this first pull takes the longest (about ~5 minutes)

```bash
kubectl apply -f ./crd/amg2023.yaml
time kubectl wait --for=condition=ready pod -l job-name=flux-sample --timeout=600s
```
4 min 58 seconds

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
  flux run -N 16 -n 128 -g 1 amg -P 4 4 8 -n 64 128 128 |& tee ./$output/$app-$size-iter-${i}.out
done

oras push ghcr.io/converged-computing/metrics-operator-experiments/performance:test-$app $output
```

On two nodes this problem is almost instant.

```bash
kubectl delete -f ./crd/amg2023.yaml
```

### 3. Kripke

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
  time flux run -N16 -n 128 -g 1 -o gpu-affinity=per-task kripke --arch CUDA --layout GDZ --dset 8 --zones 128,128,128 --gset 16 --groups 64 --niter 10 --legendre 9 --quad 8 --procs 4,4,8  |& tee ./$output/$app-16-iter-${i}.out

 time flux run -N8 -n 64 -g 1 -o gpu-affinity=per-task kripke --arch CUDA --layout GDZ --dset 8 --zones 128,128,128 --gset 16 --groups 64 --niter 10 --legendre 9 --quad 8 --procs 4,4,4 |& tee ./$output/$app-8-iter-${i}.out

 time flux run -N4 -n 32 -g 1 -o gpu-affinity=per-task kripke --arch CUDA --layout GDZ --dset 8 --zones 128,128,128 --gset 16 --groups 64 --niter 10 --legendre 9 --quad 8 --procs 4,4,2 |& tee ./$output/$app-4-iter-${i}.out
done

oras push ghcr.io/converged-computing/metrics-operator-experiments/performance:test-$app $output
```

```bash
kubectl delete -f ./crd/kripke.yaml
```

Times:

 - 16 nodes: 23 seconds
 - 8 nodes: 41 seconds
 - 4 nodes: 1m 28s


### 4. Laghos

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
  time flux run -N16 -n 128 -g 1 /opt/laghos/cuda/laghos -p 1 -m ./data/cube01_hex.mesh -rs 2 -tf 0.6 -pa -cfl 0.08 --max-steps 20 |& tee ./$output/$app-$size-iter-${i}.out
done

oras push ghcr.io/converged-computing/metrics-operator-experiments/performance:test-$app $output
```

This might be a problem:

```console
MPI is NOT CUDA aware
```

Note that I stopped here, went back and rebuilt all containers, adding oras and removing mpich and the associated library.

Times for 20 max steps:

  - 4 nodes: 36 seconds
  - 8 nodes: 30 seconds 
  - 16 nodes: 58 seconds

```bash
kubectl delete -f ./crd/laghos.yaml
```


### 5. LAMMPS

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
# 53 seconds on lassen 2 nods
# 
mkdir -p $output
for i in $(seq 1 2); do     
  echo "Running iteration $i"
  flux run -N2  -n 8 -g 1 lmp -k on g 4 -sf kk -pk kokkos newton on neigh half -in in.snap.test -var snapdir 2J8_W.SNAP -v x 228 -v y 228 -v z 228 -var nsteps 20000  |& tee ./$output/$app-$size-iter-${i}.out
done

oras push ghcr.io/converged-computing/metrics-operator-experiments/performance:test-$app $output
```

```bash
kubectl delete -f ./crd/lammps.yaml
```


### 6. Magma

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
  flux run -N2 -n 8 -g 1 -o gpu-affinity=per-task /opt/magma/magma-2.8.0/build/testing/testing_dgemm |& tee ./$output/$app-$size-iter-${i}.out
done

oras push ghcr.io/converged-computing/metrics-operator-experiments/performance:test-$app $output
```

Other commands

```bash
flux run -N2 -n 8 -g 1 -o gpu-affinity=per-task /opt/magma/magma-2.8.0/build/testing/testing_dgemm
time flux run -N1 -n 4 -g 1 -o gpu-affinity=per-task /opt/magma/magma-2.8.0/build/testing/testing_dgemm --ngpu 1

# Note this seemed to allow running across gpu (the --gpus 4 worked) but in practice we didn't see them running.
# export MAGMA_NUM_GPUS=4
time flux run -N2 -n 8 -g 1 -o gpu-affinity=per-task /opt/magma/magma-2.8.0/build/testing/testing_dgemm_vbatched --ngpu 1
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

### 7. MiniFE


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
  flux run -N2 -n 8 -g 1 -o gpu-affinity=per-task miniFE.x nx=620 ny=620 nz=620 num_devices=4 use_locking=1 elem_group_size=2 use_elem_mat_fields=10 verify_solution=0 |& tee ./$output/$app-$size-iter-${i}.out
done

oras push ghcr.io/converged-computing/metrics-operator-experiments/performance:test-$app $output
```

```bash
kubectl delete -f ./crd/minife.yaml
```

### 8. Mixbench

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
  flux run -N2 -n 8 -g 1 ./wrapper 64 |& tee ./$output/$app-$size-iter-${i}.out
done

oras push ghcr.io/converged-computing/metrics-operator-experiments/performance:test-$app $output
```

```bash
kubectl delete -f ./crd/mixbench.yaml
```


### 9. Mt Gem


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
  flux run -N2 -n 8 -g 1 /opt/gem/mt-dgemm.x 8192 200 |& tee ./$output/$app-$size-iter-${i}.out
done

oras push ghcr.io/converged-computing/metrics-operator-experiments/performance:test-$app $output
```

```bash
kubectl delete -f ./crd/mt-gem.yaml
```

### 10. Multi GPU Models

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
flux run -N2 -n 8 -g 1 /opt/multi-gpu-programming-models/mpi/jacobi -niter 5000

# 50 seconds
flux run -N2 -n 8 -g 1 /opt/multi-gpu-programming-models/mpi/jacobi -niter 10000

# 1 minute 36 seconds
flux run -N2 -n 8 -g 1 /opt/multi-gpu-programming-models/mpi/jacobi -niter 10000
```


```bash
kubectl delete -f ./crd/multi-gpu-models.yaml
```


### 11. Nek5000

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
  flux run -N2 -n 8 -g 1 nekrs --setup turbPipe.par |& tee ./$output/$app-$size-iter-${i}.out
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
flux run -N1 -n 4 -g 1 nekrs --setup turbPipe.par
flux run -N2 -n 8 -g 1 nekrs --setup turbPipe.par
```

```bash
kubectl delete -f ./crd/nek5000.yaml
```


### 12. OSU

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
  flux run -N2 -n2 -g 1 /opt/osu-benchmark/build.openmpi/mpi/pt2pt/osu_bw -d cuda D D |& tee ./$output/$app-osu_bw-$size-iter-${i}.out
  flux run -N2 -n8 -g 1 -o gpu-affinity=per-task /opt/osu-benchmark/build.openmpi/mpi/collective/osu_allreduce -d cuda D D |& tee ./$output/$app-osu_allreduce-$size-iter-${i}.out
  flux run -N2 -n2 -g 1 -o gpu-affinity=per-task /opt/osu-benchmark/build.openmpi/mpi/pt2pt/osu_latency -d cuda D D |& tee ./$output/$app-osu_latency-$size-iter-${i}.out
done

oras push ghcr.io/converged-computing/metrics-operator-experiments/performance:test-$app $output
```

```bash
kubectl delete -f ./crd/osu.yaml
```

### 13. Quicksilver

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
  flux run -N2 -n 8 -g 1 qs --inputFile /opt/quicksilver/Examples/CORAL2_Benchmark/Problem1/Coral2_P1.inp  |& tee ./$output/$app-$size-iter-${i}.out
done

oras push ghcr.io/converged-computing/metrics-operator-experiments/performance:test-$app $output
```

Both options:

```bash
flux run -N2 -n 8 -g 1 qs --inputFile /opt/quicksilver/Examples/CORAL2_Benchmark/Problem1/Coral2_P1.inp

# Coral 2 example
flux run -N2 -n 8 -g 1 qs --inputFile /opt/quicksilver/Examples/CORAL2_Benchmark/Problem2/Coral2_P2.inp
```

```bash
kubectl delete -f ./crd/quicksilver.yaml
```

### 14. Resnet

```bash
kubectl apply -f ./crd/resnet.yaml
time kubectl wait --for=condition=ready pod -l job-name=flux-sample --timeout=600s
```

```bash
flux proxy local:///mnt/flux/view/run/flux/local bash
```

```console
oras login ghcr.io --username vsoch
app=resnet
output=./results/$app

mkdir -p $output
for i in $(seq 1 2); do     
  echo "Running iteration $i"
  flux run -N 2 --gpus-per-node 4 /bin/bash ./launch.sh flux-sample 2 4 16 |& tee ./$output/$app-$size-iter-${i}.out
done

oras push ghcr.io/converged-computing/metrics-operator-experiments/performance:test-$app $output
```

```bash
kubectl delete -f ./crd/resnet.yaml
```


### 15. Stream

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
  flux run -N2 -n 8 -g 1 -o gpu-affinity=per-task stream  |& tee ./$output/$app-$size-iter-${i}.out
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
