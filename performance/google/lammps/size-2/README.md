# LAMMPS on Kubernetes

> V100 nodes

We have two containers to test here, one with Kokkos, and one without.

 - Without Kokkos: pull time is approximately 2m 45seconds

Let's also try adding the [GPU Operator](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/23.9.2/google-gke.html)

```bash
GOOGLE_PROJECT=myproject
gcloud beta container clusters create test-cluster \
      --project ${GOOGLE_PROJECT} \
      --zone us-central1-a \
      --threads-per-core=1 \
      --release-channel "regular" \
      --machine-type "n1-standard-32" \
      --accelerator "type=nvidia-tesla-v100,count=4" \
      --image-type "UBUNTU_CONTAINERD" \
      --disk-type "pd-standard" \
      --disk-size "1000" \
      --metadata disable-legacy-endpoints=true \
      --max-pods-per-node "110" \
      --num-nodes "2" \
      --enable-ip-alias \
      --no-enable-intra-node-visibility \
      --default-max-pods-per-node "110" \
      --no-enable-master-authorized-networks \
      --tags=nvidia-ingress-all
```
- pull to running time: 18 seconds (included layers from multi-gpu-benchmarks

We have to be sure the nodes have gpu. This is wrong:

```bash
$ kubectl get nodes -o json | jq .items[].status.allocatable
```

Create the GPU operator.

```bash
kubectl apply -f gpu-operator.yaml
```

Install helm for it

```
helm repo add nvidia https://helm.ngc.nvidia.com/nvidia \
    && helm repo update

helm install --wait --generate-name \
    -n gpu-operator --create-namespace \
    nvidia/gpu-operator
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
# Need to rebuild and test this for hackathon.
lmp_gpu -in in.snap.test -var snapdir 2J8_W.SNAP -v x 2 -v y 2 -v z -var nsteps 1000

# Two nodes with flux (utilization at about 22%)
flux run -N2 -n 8 -g 1 lmp -k on g 4 -sf kk -pk kokkos newton on neigh half -in in.snap.test -var snapdir 2J8_W.SNAP -v x 64 -v y 64 -v z 64 -var nsteps 1000
```

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
