# JobSet vs. Flux Operator

Let's look at a comparison between using JobSet and the flux operator. Why not. This will start with 4 nodes and CPU.

## Usage

### CPU

If you are creating a CPU cluster (note that I haven't tested on this):

```bash
GOOGLE_PROJECT=myproject
gcloud container clusters create test-cluster \
    --threads-per-core=1 \
    --placement-type=COMPACT \
    --num-nodes=5 \
    --region=us-central1-a \
    --project=${GOOGLE_PROJECT} \
    --machine-type=c2d-standard-32
```

This is how to connect to the proxy with CPU

```bash
. /mnt/flux/flux-view.sh 
flux proxy $fluxsocket bash
```

## GPU

And a GPU cluster:

```bash
GOOGLE_PROJECT=myproject
gcloud container clusters create test-cluster --threads-per-core=1 --accelerator type=nvidia-tesla-v100,count=4 --num-nodes=2 --machine-type=n1-standard-32 --region=us-central1-a --project=${GOOGLE_PROJECT} 
```

Install drivers:

```bash
kubectl apply -f daemonset.yaml
```
This is now correct to show nvidia.com/gpu: 4 for each.

```bash
kubectl get nodes -o json | jq .items[].status.allocatable
```

This is how to connect to the proxy with GPU:

```
kubectl exec -it flux-sample-0-qdckd bash
flux proxy local:///mnt/flux/view/run/flux/local bash
```

### Operators

Install the flux operator and install Jobset:

```bash
kubectl apply -f https://raw.githubusercontent.com/flux-framework/flux-operator/main/examples/dist/flux-operator.yaml
kubectl apply --server-side -f https://github.com/kubernetes-sigs/jobset/releases/download/v0.5.0/manifests.yaml
```

### Test 

These will be static (and somewhat interactive) runs to test. Try creating the jobset

```bash
kubectl apply -f ./crd/minicluster.yaml
```

Here is to run with 2 nodes:

```bash
# job name for service, number of nodes, processes per node, and batch size
flux submit --watch -N 2 --gpus-per-node 4 /bin/bash ./launch.sh flux-sample 2 4 16
```

### Clean Up

When you are done:

```bash
gcloud container clusters delete test-cluster --region=us-central1-a
```

This would be a production cluster (of some size)

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
    --system-config-from-file=./system-config.yaml
```

