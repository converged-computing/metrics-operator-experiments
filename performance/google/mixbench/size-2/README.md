# Mixbench on Kubernetes

> V100 nodes
- https://github.com/ekondis/mixbench/tree/master

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
mixbench-cuda

# 21.9 seconds on 2 node, 8 gpu
flux run -N2 -n 8 -g 1 ./wrapper 64

# 25.8 seconds
flux run -N2 -n 8 -g 1 ./wrapper 64
```

Note that it looks like this is intended to run on one node, so the correct means to run is probably just:

```
mixbench-cuda
mixbench-cpu
```

### Clean Up

When you are done:

```bash
gcloud container clusters delete test-cluster --region=us-central1-a
```
