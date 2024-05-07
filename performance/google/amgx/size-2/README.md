# Amgx on Kubernetes

> V100 nodes

Here we are trying to use v100 for [amgx](https://github.com/NVIDIA/AMGX). The [container is here](https://github.com/converged-computing/metrics-operator-experiments/pkgs/container/metric-amgx).

```bash
GOOGLE_PROJECT=myproject
gcloud container clusters create test-cluster --threads-per-core=1 --accelerator type=nvidia-tesla-v100,count=4 --num-nodes=2 --machine-type=n1-standard-32 --region=us-central1-a --project=${GOOGLE_PROJECT} 
```
- pull to running time: 18 seconds (included layers from multi-gpu-benchmarks

We have to be sure the nodes have gpu. This is wrong:

```bash
$ kubectl get nodes -o json | jq .items[].status.allocatable
```
```console
{
  "cpu": "15890m",
  "ephemeral-storage": "47060071478",
  "hugepages-1Gi": "0",
  "hugepages-2Mi": "0",
  "memory": "114327136Ki",
  "pods": "110"
}
{
  "cpu": "15890m",
  "ephemeral-storage": "47060071478",
  "hugepages-1Gi": "0",
  "hugepages-2Mi": "0",
  "memory": "114327136Ki",
  "pods": "110"
}
```

What I had to do is install a custom daemonset that would install the driver:

```bash
kubectl apply -f daemonset.yaml
```

Check the log to see it installed:

```bash
kubectl logs -n kube-system nvidia-driver-installer-94v2h 
```
```console
I0427 01:52:44.079644    8897 modules.go:50] Updating host's ld cache
```

This is now correct!

```bash
$ kubectl get nodes -o json | jq .items[].status.allocatable
```
```console
{
  "cpu": "15890m",
  "ephemeral-storage": "47060071478",
  "hugepages-1Gi": "0",
  "hugepages-2Mi": "0",
  "memory": "114327136Ki",
  "nvidia.com/gpu": "4",
  "pods": "110"
}
{
  "cpu": "15890m",
  "ephemeral-storage": "47060071478",
  "hugepages-1Gi": "0",
  "hugepages-2Mi": "0",
  "memory": "114327136Ki",
  "nvidia.com/gpu": "4",
  "pods": "110"
}
```

Install the flux operator:

```bash
kubectl apply -f https://raw.githubusercontent.com/flux-framework/flux-operator/main/examples/dist/flux-operator.yaml
```

And create the minicluster:

```bash
kubectl apply -f minicluster.yaml
```

But this should be fine for now, we can test either, and in either we can re-generate the R to target the GPU. It's interactive, so shell inside:

```bash
kubectl exec -it flux-sample-0-qdckd bash
flux proxy local:///mnt/flux/view/run/flux/local bash
```

You should see the GPU in the resources:

```bash
flux resource list
```
```console
# flux resource list
     STATE NNODES   NCORES    NGPUS NODELIST
      free      1        6        1 flux-sample-0
 allocated      0        0        0 
      down      0        0        0 
```

Single GPU example (in ./build)

```bash
# Single GPU
./examples/amgx_capi -m ../examples/matrix.mtx -c ../src/configs/FGMRES_AGGREGATION.json

# Multiple GPU (2,3) seem to work (still too fast, almost instant)
mpirun --allow-run-as-root -n 2 examples/amgx_mpi_capi -m ../examples/matrix.mtx -c ../src/configs/FGMRES_AGGREGATION.json
mpirun --allow-run-as-root -n 3 examples/amgx_mpi_capi -m ../examples/matrix.mtx -c ../src/configs/FGMRES_AGGREGATION.json

# 4 GPU does not converge
mpirun --allow-run-as-root -n 4 examples/amgx_mpi_capi -m ../examples/matrix.mtx -c ../src/configs/FGMRES_AGGREGATION.json

# Flux with one node (does not converge with 4)
flux run -N1 -n 3 -g 1 ./examples/amgx_mpi_capi -m ../examples/matrix.mtx -c ../src/configs/FGMRES_AGGREGATION.json

# Two nodes
flux run -N2 -n 8 -g 1 ./examples/amgx_mpi_capi -m ../examples/matrix.mtx -c ../src/configs/FGMRES_AGGREGATION.json
```

### Clean Up

When you are done:

```bash
gcloud container clusters delete test-cluster --region=us-central1-a
```
