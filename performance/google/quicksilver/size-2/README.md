# Quicksilver on Kubernetes

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

Single GPU example (in ./build)

```bash
# Local test
qs /opt/quicksilver/Examples/CORAL2_Benchmark/Problem1/Coral2_P1.inp

# Flux with one node and two nodes
flux run -N2 -n 8 -g 1 qs /opt/quicksilver/Examples/CORAL2_Benchmark/Problem1/Coral2_P1.inp

# Coral 2 example
flux run -N2 -n 8 -g 1 qs /opt/quicksilver/Examples/CORAL2_Benchmark/Problem2/Coral2_P2.inp

# All examples:
# /opt/quicksilver/Examples/AllScattering/scatteringOnly.inp
# /opt/quicksilver/Examples/NoCollisions/no.collisions.inp
# /opt/quicksilver/Examples/NonFlatXC/NonFlatXC.inp
# /opt/quicksilver/Examples/CORAL2_Benchmark/Problem2/Coral2_P2_4096.inp
# /opt/quicksilver/Examples/CORAL2_Benchmark/Problem2/Coral2_P2.inp
# /opt/quicksilver/Examples/CORAL2_Benchmark/Problem2/Coral2_P2_1.inp
# /opt/quicksilver/Examples/CORAL2_Benchmark/Problem1/Coral2_P1.inp
# /opt/quicksilver/Examples/CORAL2_Benchmark/Problem1/Coral2_P1_1.inp
# /opt/quicksilver/Examples/CORAL2_Benchmark/Problem1/Coral2_P1_4096.inp
# /opt/quicksilver/Examples/CTS2_Benchmark/CTS2.inp
# /opt/quicksilver/Examples/CTS2_Benchmark/CTS2_36.inp
# /opt/quicksilver/Examples/CTS2_Benchmark/CTS2_1.inp
# /opt/quicksilver/Examples/AllAbsorb/allAbsorb.inp
# /opt/quicksilver/Examples/Homogeneous/homogeneousProblem_v4_ts.inp
# /opt/quicksilver/Examples/Homogeneous/homogeneousProblem_v5_ts.inp
# /opt/quicksilver/Examples/Homogeneous/homogeneousProblem.inp
# /opt/quicksilver/Examples/Homogeneous/homogeneousProblem_v3_wq.inp
# /opt/quicksilver/Examples/Homogeneous/homogeneousProblem_v7_ts.inp
# /opt/quicksilver/Examples/Homogeneous/homogeneousProblem_v4_tm.inp
# /opt/quicksilver/Examples/Homogeneous/homogeneousProblem_v3.inp
# /opt/quicksilver/Examples/AllEscape/allEscape.inp
# /opt/quicksilver/Examples/NoFission/noFission.inp

```

### Clean Up

When you are done:

```bash
gcloud container clusters delete test-cluster --region=us-central1-a
```
