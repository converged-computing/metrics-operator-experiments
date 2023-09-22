# Additional Volume Setups

In addition to the already implemented described in [run1](../run1), I'd like to focus
on benchmarking single node for [provided storage solutions](https://cloud.google.com/kubernetes-engine/docs/concepts/storage-overview)
meaning we don't have to setup our own filesystem in addition.

## Contenders

### Block Storage Persistent Disk

 - Includes filestore (already ready to go for experiment)
 - [Cloud Volumes Service](https://netapp-trident.readthedocs.io/en/stable-v20.01/kubernetes/operations/tasks/backends/cvs_gcp.html) (requires external service, no)
 - [Google Compute Engine Persistent Disk](https://cloud.google.com/kubernetes-engine/docs/how-to/persistent-volumes/gce-pd-csi-driver) TODO try this.
  
## Choices

These are the ones I want to test. Filestore was already tested in [run0](run0) and
the yamls are included here in [crd](crd). We need to figure out the rest.

### Persistent Volumes

We are going to try a vanilla cluster as described in the [docs](https://cloud.google.com/kubernetes-engine/docs/how-to/persistent-volumes/gce-pd-csi-driver) first:

#### 1. Create Cluster

```bash
gcloud container clusters create storage-cluster \
   --addons=GcePersistentDiskCsiDriver \
  --machine-type=c2d-standard-2
```

#### 2. Get Storageclass

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

Let's create additional ones we can ask for. Note that [we cannot use the c3 type](https://cloud.google.com/kubernetes-engine/docs/how-to/persistent-volumes/gce-pd-csi-driver#unsupported_machine_types).


TODO I think I need to [create a persistent disk](https://cloud.google.com/compute/docs/disks/extreme-persistent-disk#provisioning_iops) too.
This means we can ask for any three of these volumes, and 
