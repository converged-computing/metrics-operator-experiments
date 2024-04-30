# Pennant Testing on Kubernetes

> V100 nodes

Here we are trying to run the Nvidia multi-gpu-benchmarks on two nodes, each with 4 GPU. We currently have a quota of 8 so 2x4 is the max we can do at about [$20/hour](https://cloud.google.com/products/calculator/#id=d83978ea-811c-494e-95cc-9af9f1fdc6a4).

```bash
GOOGLE_PROJECT=myproject
time gcloud container clusters create test-cluster --threads-per-core=1 --accelerator type=nvidia-tesla-v100,count=4 --num-nodes=2 --machine-type=n1-standard-32 --region=us-central1-a --project=${GOOGLE_PROJECT} 
```

The [container is here](https://github.com/converged-computing/metrics-operator-experiments/pkgs/container/multi-gpu-models)

## Timing

- create cluster: ~5 minutes
- pull container through running: 2 minutes 30 seconds
- install stuff / daemonset checking: ~2 minutes

Install the drivers:

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
kubectl get nodes -o json | jq .items[].status.allocatable
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

Interactively shell to test, etc.

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

Here is how to run on one and two nodes:

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

### Clean Up

When you are done:

```bash
gcloud container clusters delete test-cluster --region=us-central1-a
```
