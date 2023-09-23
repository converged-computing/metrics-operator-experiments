# Additional Volume Setups

In addition to the already implemented described in [run1](../run1), I'd like to focus
on benchmarking single node for [provided storage solutions](https://cloud.google.com/kubernetes-engine/docs/concepts/storage-overview)
meaning we don't have to setup our own filesystem in addition.

## Contenders

### Block Storage Persistent Disk

 - Includes filestore (already ready to go for experiment)
 - [Cloud Volumes Service](https://netapp-trident.readthedocs.io/en/stable-v20.01/kubernetes/operations/tasks/backends/cvs_gcp.html) (requires external service, no)
 - [Google Compute Engine Persistent Disk](https://cloud.google.com/kubernetes-engine/docs/how-to/persistent-volumes/gce-pd-csi-driver)
  
## Choices

These are the ones I want to test. While we tested some early in [run0](run0), since we updated the operator and have a new set of experiments (that I want to better automate) we will do this again.

 - Filestore
 - Peristent Disks
 - Fuse to Google Storage
 
## Install Metrics Operator

This is a shared section that will be referenced to install the operator. You will be directed
to do this after creating the cluster(s) below!  We are going to do all the types again because it's an updated version, and also use the development release (not merged yet). We need jobset first:

```bash
VERSION=v0.2.0
kubectl apply --server-side -f https://github.com/kubernetes-sigs/jobset/releases/download/$VERSION/manifests.yaml
```

And then the operator:

```bash
kubectl apply -f ./operator/metrics-operator-dev.yaml
```

## Filestore

Let's create a cluster with the Filestore addon.

```bash
GOOGLE_PROJECT=myproject
gcloud container clusters create storage-cluster \
   --addons=GcpFilestoreCsiDriver \
   --machine-type=c2d-standard-8 \
   --region=us-central1-a \
   --num-nodes=3
   # This is the default, but be explicit
```

When it's done, you will want to [install the metrics operator](#install-metrics-operator).


### 2. Get Storageclass

Get the storage classes available for Filestore. I didn't consider this before, but likely we want to test Filestore with different classes.

```bash
kubectl get sc
```
```console
NAME                        PROVISIONER                    RECLAIMPOLICY   VOLUMEBINDINGMODE      ALLOWVOLUMEEXPANSION   AGE
enterprise-multishare-rwx   filestore.csi.storage.gke.io   Delete          WaitForFirstConsumer   true                   3m12s
enterprise-rwx              filestore.csi.storage.gke.io   Delete          WaitForFirstConsumer   true                   3m11s
premium-rwo                 pd.csi.storage.gke.io          Delete          WaitForFirstConsumer   true                   2m44s
premium-rwx                 filestore.csi.storage.gke.io   Delete          WaitForFirstConsumer   true                   3m12s
standard                    kubernetes.io/gce-pd           Delete          Immediate              true                   2m44s
standard-rwo (default)      pd.csi.storage.gke.io          Delete          WaitForFirstConsumer   true                   2m44s
standard-rwx                filestore.csi.storage.gke.io   Delete          WaitForFirstConsumer   true                   3m12s
zonal-rwx                   filestore.csi.storage.gke.io   Delete          WaitForFirstConsumer   true                   3m11s
```

I'm also realizing now we should be testing the different rwx (read write many) classes.

### Filestore Tets

Let's test filestore. First create the PVCs, one for each of the rwx classes.

```bash
kubectl apply -f ./crd/filestore/pvc-filestore-standard.yaml
kubectl apply -f ./crd/filestore/pvc-filestore-premium.yaml
```

And then we will run a manual test. Note that I'm doing
this first, and then will automate running the scripts (and saving output, of course).
This uses the standard-rwx

```bash
kubectl apply -f ./crd/filestore/big-file-sequential-read.yaml
```

### x. Clean up

When you are done:

```bash
gcloud container clusters delete storage-cluster --region us-central1-a --quiet
```


## Peristent Disk

### 0. Workload Identity

You'll need to [set this up](https://cloud.google.com/kubernetes-engine/docs/how-to/workload-identity#authenticating_to). I've done this already for a different project so I was good. :)
It looks

### 1. Create

Three nodes is the default, but we can be explicit.

```bash
GOOGLE_PROJECT=myproject
gcloud container clusters create storage-cluster \
   --addons=GcePersistentDiskCsiDriver \
   --addons GcsFuseCsiDriver \
   --machine-type=c2d-standard-8 \
   --region=us-central1-a \
   --workload-pool=${GOOGLE_PROJECT}.svc.id.goog \
   --num-nodes=3
   # This is the default, but be explicit
```

Create a service account (sa) in the default namespace:

```bash
kubectl create serviceaccount metrics-operator-sa
```

And then enabling to use workload identity ([instructions](https://cloud.google.com/kubernetes-engine/docs/how-to/persistent-volumes/cloud-storage-fuse-csi-driver#provision-static)):

```bash
gcloud container clusters get-credentials storage-cluster --region=us-central1-a
```

We can create (or get an existing) service account:

```bash
gcloud iam service-accounts create metrics-operator-sa --project=$GOOGLE_PROJECT
```

Give it permission to access storage buckets:

```bash
gcloud projects add-iam-policy-binding ${GOOGLE_PROJECT} --member "serviceAccount:metrics-operator-sa@${GOOGLE_PROJECT}.iam.gserviceaccount.com" --role roles/storage.objectAdmin
```

Allow the Kubernetes service account to impersonate it:

```bash
gcloud iam service-accounts add-iam-policy-binding metrics-operator-sa@${GOOGLE_PROJECT}.iam.gserviceaccount.com \
    --role roles/iam.workloadIdentityUser \
    --member "serviceAccount:$GOOGLE_PROJECT.svc.id.goog[default/metrics-operator-sa]"
```

Annotate the service account with the email of the IAM service account:

```bash
kubectl annotate serviceaccount metrics-operator-sa iam.gke.io/gcp-service-account=metrics-operator-sa@${GOOGLE_PROJECT}.iam.gserviceaccount.com
```

### 2. Get Storageclass

Get the storage classes available. We will want to prepare files (storage classes) for each.

```bash
kubectl get sc
```
```console
NAME                     PROVISIONER             RECLAIMPOLICY   VOLUMEBINDINGMODE      ALLOWVOLUMEEXPANSION   AGE
premium-rwo              pd.csi.storage.gke.io   Delete          WaitForFirstConsumer   true                   2m2s
standard                 kubernetes.io/gce-pd    Delete          Immediate              true                   2m1s
standard-rwo (default)   pd.csi.storage.gke.io   Delete          WaitForFirstConsumer   true                   2m1s
```

Let's create additional ones we can ask for. Note that [we cannot use the c3 type](https://cloud.google.com/kubernetes-engine/docs/how-to/persistent-volumes/gce-pd-csi-driver#unsupported_machine_types). Let's create a few new ones:

```bash
kubectl  apply -f ./crd/persistent-volumes-storage-class/pd-balanced.yaml 
kubectl  apply -f ./crd/persistent-volumes-storage-class/pd-ssd.yaml 
kubectl  apply -f ./crd/persistent-volumes-storage-class/pd-extreme.yaml 
```
And see the new classes:

```bash
kubectl get sc
```
```console
NAME                     PROVISIONER             RECLAIMPOLICY   VOLUMEBINDINGMODE      ALLOWVOLUMEEXPANSION   AGE
pd-balanced              pd.csi.storage.gke.io   Delete          WaitForFirstConsumer   true                   38s
pd-extreme               pd.csi.storage.gke.io   Delete          WaitForFirstConsumer   true                   29s
pd-ssd                   pd.csi.storage.gke.io   Delete          WaitForFirstConsumer   true                   32s
premium-rwo              pd.csi.storage.gke.io   Delete          WaitForFirstConsumer   true                   18m
standard                 kubernetes.io/gce-pd    Delete          Immediate              true                   18m
standard-rwo (default)   pd.csi.storage.gke.io   Delete          WaitForFirstConsumer   true                   18m
```


## Testing Volumes

Now let's test our basic setups (that worked before).

### x. Clean up

When you are done:

```bash
gcloud container clusters delete storage-cluster --region us-central1-a --force
```

### Persistent Volumes

We are going to try a vanilla cluster as described in the [docs](https://cloud.google.com/kubernetes-engine/docs/how-to/persistent-volumes/gce-pd-csi-driver) first:



TODO I think I need to [create a persistent disk](https://cloud.google.com/compute/docs/disks/extreme-persistent-disk#provisioning_iops) too.
This means we can ask for any three of these volumes, and 
