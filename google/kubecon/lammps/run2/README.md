# Lammps Automated

This will only be running automated lammps on a very large cluster size (128).

 - c3-standard-176 is USD 5.08 for 1 node over 1 hour
 - TIER-1 is usually half the cost of the total cluster (at least before)
 
If I take 129 nodes this is ~$ 650.84/hour (rounded up)  and 2 hours would be $1,301.68.
I'm going to assume ~85/hour for TIER-1 networking (about half). Here is a small table I can keep track of times / costs.

I absolutely cannot go over that. What I'm going to do is quickly bring up the cluster and immediately test on size 128.
If it doesn't work, I'm going to immediately bring it down and do the same experiment on size 64 first.
Note that the c2d-standard-112 instance type has:

 - 112 vCPU which is 56 actual cores
 - 448 GB memory

If I finish quickly, I'll try a large problem size or two (that failed on c3) although I don't expect a different outcome. :)
See [run1](../run1) for original notes and planning.

| Time | Event |
| -----|-------|
| 11:40am | Bring up cluster |


## Experiments

### Create the Cluster

Let's test a cluster on c3-standard-176 for size 17.
We are following [these best practices](https://cloud.google.com/architecture/best-practices-for-using-mpi-on-compute-engine).

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
    --system-config-from-file=./crd/system-config.yaml
```

And save metadata about the nodes.

```bash
mkdir -p ./data
kubectl get nodes -o json > data/nodes.json
```

Install the Metrics Operator SDK. Version 19 has added support for custom (raw) log parsing.

```bash
pip install metricsoperator==0.0.19
```

### 2. Setup the Metrics Operator

Install JobSet first:

```bash
VERSION=v0.2.0
kubectl apply --server-side -f https://github.com/kubernetes-sigs/jobset/releases/download/$VERSION/manifests.yaml
```

Then install the metrics operator. 

```bash
$ kubectl apply -f ./operator/metrics-operator.yaml
```

#### 1. LAMMPS Automated

For running lammps at different sizes, we can use the script. I am only running a problem size 2x2x2 that
I know will run at the smaller sizes and complete, the idea being that we want to see how large this
can go before it stops working.


```bash
mkdir -p ./data/lammps

# This is my mistake - I should have told the operators to be scheduled on ONE node, or asked for 2 additional ones
# note that this data file is saved to crd-lammps-lammps-small-128-shared-node.json
time python run-lammps.py --iter 2 --out ./data/lammps --input ./crd/lammps/lammps-small-128.yaml --sleep 60   12 minutes each

# Note that for this run I verified the nodes were not running on any nodes with an operator pod scheduled
time python run-lammps.py --iter 2 --out ./data/lammps --input ./crd/lammps/lammps-small-127.yaml --sleep 5 6 minutes 
time python run-lammps.py --iter 2 --out ./data/lammps --input ./crd/lammps/lammps-small-126.yaml --sleep 5 40 seconds
time python run-lammps.py --iter 2 --out ./data/lammps --input ./crd/lammps/lammps-small-124.yaml --sleep 5 38 seconds
time python run-lammps.py --iter 2 --out ./data/lammps --input ./crd/lammps/lammps-small-120.yaml --sleep 5 38 seconds
time python run-lammps.py --iter 2 --out ./data/lammps --input ./crd/lammps/lammps-small-112.yaml --sleep 5 35 seconds
time python run-lammps.py --iter 2 --out ./data/lammps --input ./crd/lammps/lammps-small-96.yaml --sleep 5  31 seconds?
time python run-lammps.py --iter 2 --out ./data/lammps --input ./crd/lammps/lammps-small-64.yaml --sleep 5  24 seconds each
time python run-lammps.py --iter 3 --out ./data/lammps --input ./crd/lammps/lammps-small-32.yaml --sleep 5  14 seconds each
time python run-lammps.py --iter 3 --out ./data/lammps --input ./crd/lammps/lammps-small-16.yaml --sleep 5  10 seconds each
time python run-lammps.py --iter 3 --out ./data/lammps --input ./crd/lammps/lammps-small-8.yaml --sleep 5   5 seconds each 
time python run-lammps.py --iter 3 --out ./data/lammps --input ./crd/lammps/lammps-small-4.yaml --sleep 5   7 seconds each
time python run-lammps.py --iter 3 --out ./data/lammps --input ./crd/lammps/lammps-small-2.yaml --sleep 5   4 seconds each
time python run-lammps.py --iter 3 --out ./data/lammps --input ./crd/lammps/lammps-small-1.yaml --sleep 5   2 seconds each
```

I'm worried for the size 128 there was an issue of a shared node. I tried to explicitly ensure that doesn't happen by putting the two operators on the same node, but my effort failed. Before I do that, for the comment above, JobSet is running here:

```
NAME                                         READY   STATUS    RESTARTS   AGE   IP         NODE                                          NOMINATED NODE   READINESS GATES
jobset-controller-manager-598f89f884-wdhtt   2/2     Running   0          61m   10.8.1.4   gke-test-cluster-default-pool-0b9fe0dd-032c   <none>           <none>
```

And metrics operator here:

```
NAME                                          READY   STATUS    RESTARTS   AGE   IP           NODE                                          NOMINATED NODE   READINESS GATES
metrics-controller-manager-775bb5f45c-lcpkh   2/2     Running   0          61m   10.8.122.3   gke-test-cluster-default-pool-0b9fe0dd-x27g   <none>           <none>
```

I tried deleting:

```bash
VERSION=v0.2.0
kubectl delete -f https://github.com/kubernetes-sigs/jobset/releases/download/$VERSION/manifests.yaml
kubectl delete -f ./operator/metrics-operator.yaml
```

And then labeling a node to schedule operators on:

```bash
kubectl label nodes gke-test-cluster-default-pool-0b9fe0dd-032c operators=yes
kubectl  get node gke-test-cluster-default-pool-0b9fe0dd-032c -o json > data/labeled-node.json
```

But then the application did not work:

```
cd ./operator/labeled
kubectl apply -f jobset-operator.yaml
kubectl delete -f metrics-operator.yaml
```
```console
serviceaccount/jobset-controller-manager created
role.rbac.authorization.k8s.io/jobset-leader-election-role created
clusterrole.rbac.authorization.k8s.io/jobset-manager-role created
clusterrole.rbac.authorization.k8s.io/jobset-metrics-reader created
clusterrole.rbac.authorization.k8s.io/jobset-proxy-role created
rolebinding.rbac.authorization.k8s.io/jobset-leader-election-rolebinding created
clusterrolebinding.rbac.authorization.k8s.io/jobset-manager-rolebinding created
clusterrolebinding.rbac.authorization.k8s.io/jobset-proxy-rolebinding created
secret/jobset-webhook-server-cert created
service/jobset-controller-manager-metrics-service created
service/jobset-webhook-service created
mutatingwebhookconfiguration.admissionregistration.k8s.io/jobset-mutating-webhook-configuration created
validatingwebhookconfiguration.admissionregistration.k8s.io/jobset-validating-webhook-configuration created
Error from server (Invalid): error when creating "jobset-operator.yaml": CustomResourceDefinition.apiextensions.k8s.io "jobsets.jobset.x-k8s.io" is invalid: metadata.annotations: Too long: must have at most 262144 bytes
Error from server (BadRequest): error when creating "jobset-operator.yaml": Deployment in version "v1" cannot be handled as a Deployment: json: cannot unmarshal bool into Go struct field PodSpec.spec.template.spec.nodeSelector of type string
```

I tried a bunch of derivations but nothing worked, and I couldn't keep the cluster up longer.
Note that I verified that the size 127 pods were _not_ sharing nodes with the operators, and it still slowed to 6 minutes, so this scaling issue might be real after all.

Notes:

 - A new problem I haven't seen before - will 128 concurrent pulls, I got a lot of failed image pull backoffs from ghcr.io. I had to do it twice so the containers pulled in two groups.

#### 6. Clean up

```bash
gcloud container clusters delete test-cluster --region=us-central1-a --quiet
```

And that's it!
 

## Results

### LAMMPS

```bash
mkdir -p ./img/lammps
python plot-lammps.py --results ./data/lammps --out ./img/lammps
```
