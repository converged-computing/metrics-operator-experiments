# LAMMPS on Kubernetes

> V100 nodes

```bash
GOOGLE_PROJECT=myproject
gcloud container clusters create test-cluster --threads-per-core=1 --accelerator type=nvidia-tesla-v100,count=4 --num-nodes=2 --machine-type=n1-standard-32 --region=us-central1-a --project=${GOOGLE_PROJECT} 
```

We have to be sure the nodes have gpu. This is wrong:

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

Single GPU example (in ./code)

```bash
# Two nodes with flux (utilization at about 22%)
flux run -N1 -n 4 -g 1 lmp -k on g 4 -sf kk -pk kokkos newton on neigh half -in in.snap.test -var snapdir 2J8_W.SNAP -v x 64 -v y 64 -v z 64 -var nsteps 1000
flux run -N2 -n 8 -g 1 lmp -k on g 4 -sf kk -pk kokkos newton on neigh half -in in.snap.test -var snapdir 2J8_W.SNAP -v x 64 -v y 64 -v z 64 -var nsteps 1000

# 1 minute 1 second on 2 nodes
flux run -N2  -n 8 -g 1 lmp -k on g 4 -sf kk -pk kokkos newton on neigh half -in in.snap.test -var snapdir 2J8_W.SNAP -v x 228 -v y 228 -v z 228 -var nsteps 20000
```

We aren't sure why this error happens - possibly the network. Need to test on AWS/Azure. 

```
The call to cuIpcGetMemHandle failed. This means the GPU RDMA protocol
  cuIpcGetMemHandle return value:   1
  cuIpcGetMemHandle return value:   1
cannot be used.
  address: 0x6024a8080
  address: 0x6024a8080
  cuIpcGetMemHandle return value:   1
Check the cuda.h file for what the return value means. Perhaps a reboot
Check the cuda.h file for what the return value means. Perhaps a reboot
  address: 0x6024a8080
of the node will clear the problem.
of the node will clear the problem.
Check the cuda.h file for what the return value means. Perhaps a reboot
--------------------------------------------------------------------------
--------------------------------------------------------------------------
of the node will clear the problem.
--------------------------------------------------------------------------
--------------------------------------------------------------------------
The call to cuIpcGetMemHandle failed. This means the GPU RDMA protocol
cannot be used.
  cuIpcGetMemHandle return value:   1
  address: 0x6024a8080
Check the cuda.h file for what the return value means. Perhaps a reboot
of the node will clear the problem.
```
       
### Clean Up

When you are done:

```bash
gcloud container clusters delete test-cluster --region=us-central1-a
```
