# Google Filestore Experiment with Fio 

For these experiments, we will create a small cluster on Google Cloud, and attempt
to demonstrate measuring IO stats for FIO. I'll test on a range of sizes and bytesizes.
You can read more about Fio [here](https://fio.readthedocs.io/en/latest/fio_doc.html#i-o-size).
We will be using the [FIO metric](https://converged-computing.github.io/metrics-operator/getting_started/metrics.html#fio) of the Metrics operator.
We will start with a small instance type, and likely would want to eventually vary this.

## Usage

### 1. Create the Cluster

First, create your cluster with the Filestore CSI Driver enabled. Note that I ran this command for three instance sizes,

 - n1-standard-2
 - n1-standard-8
 - n1-standard-32
 
I was mostly interested to see if there would be any (even trivial) differences.

```bash
GOOGLE_PROJECT=myproject
INSTANCE=n1-standard-2
```
```bash
$ gcloud container clusters create metrics-cluster --project $GOOGLE_PROJECT \
    --zone us-central1-a --machine-type ${INSTANCE} \
    --addons=GcpFilestoreCsiDriver \
    --num-nodes=2 --enable-network-policy --enable-intra-node-visibility
```

And then run the experiments for each instance. Note that for each instance type we will run 5x a matrix of sizes.
I chose only 3 instance types given this would be 3 x 4 x 5 == 60 runs. We can extend experiments as needed after this,
and likely we don't need two nodes.

### 2. Install JobSet

We also need to install JobSet

```bash
VERSION=v0.2.0
kubectl apply --server-side -f https://github.com/kubernetes-sigs/jobset/releases/download/$VERSION/manifests.yaml
```

### 3. Install the Metrics Operator

Let's next install the operator. You can [choose one of the options here](https://converged-computing.github.io/metrics-operator/getting_started/user-guide.html).  E.g., to deploy from the repository:

```bash
$ kubectl apply -f https://raw.githubusercontent.com/converged-computing/metrics-operator/main/examples/dist/metrics-operator.yaml
```

### 4. Prepare Filestore

Storage is neat because we can prepare several PVCs, and then have the operator test making a request to write to each one.
Create the PVC as follows:

```bash
$ kubectl apply -f pvc-filestore.yaml
```

The storage class we are testing is derived from this list:

```bash
$ kubectl get storageclass
```

And check on the status:

```bash
$ kubectl get pvc
NAME   STATUS    VOLUME   CAPACITY   ACCESS MODES   STORAGECLASS   AGE
data   Pending                                      standard-rwx   6s
```

Note that (in my experience) when you run the metrics, the Filestore takes ~3 minutes to get working. You'll want to see that the volume was provisioned
via:

```bash
kubectl describe pvc
```

Prepare a data directory for the instance:

```bash
mkdir -p data/${INSTANCE}
```

Now let's run the filestore experiment, which will request the volume and also save the metrics. Let's do this multiple times.

```bash
for i in 0 1 2 3 4; do
  echo "Running iteration $i"
  # Note that the --out is a prefix that will have the size, etc. added to it.
  python run-metric.py metrics-filestore.yaml --out ./data/${INSTANCE}/metrics-filestore-$i
done
```

## Clean Up

After we are done with filestore we can manually delete the volume (I think I forgot to add the owner reference?)

```bash
$ kubectl delete -f pvc-filestore.yaml
$ kubectl delete pv pvc-c3b2b67f-b7c7-4e67-8459-2ba84904f6d8
```

So likely you want to do this in the Google cloud console. Do the above for each instance type.
When you are done with the instance size, cleanup the cluster

```bash
$ gcloud container clusters delete metrics-cluster
```

And that's it! We will write functions to plot the results.

## Results

And plot the small results we have! I only chose attributes from read/write/trim as those seemed to be more means or averages?

```bash
python plot-results.py
```

I chose a subset of images that I thought could be compared between runs (e.g., fusion used a different cluster, and the CSI driver
was much less performant and needed a smaller problem size):

![img/read_bw_mean.png](img/read_bw_mean.png)
![img/read_bw_min.png](img/read_bw_min.png)
![img/read_bw_max.png](img/read_bw_max.png)
![img/read_iops_mean.png](img/read_iops_mean.png)
![img/read_iops_min.png](img/read_iops_min.png)
![img/read_bw_samples.png](img/read_bw_samples.png)
![img/write_iops_min.png](img/write_iops_min.png)
![img/write_iops_max.png](img/write_iops_max.png)
![img/write_bw_mean.png](img/write_bw_mean.png)
![img/write_iops.png](img/write_iops.png)
![img/write_bw_samples.png](img/write_bw_samples.png)
![img/read_iops_samples.png](img/read_iops_samples.png)
![img/read_iops_max.png](img/read_iops_max.png)
![img/read_iops.png](img/read_iops.png)
![img/read_bw_dev.png](img/read_bw_dev.png)
![img/write_bw_max.png](img/write_bw_max.png)
![img/write_bw_dev.png](img/write_bw_dev.png)
![img/read_bw.png](img/read_bw.png)
![img/write_iops_samples.png](img/write_iops_samples.png)
![img/write_bw_min.png](img/write_bw_min.png)
![img/write_io_kbytes.png](img/write_io_kbytes.png)
![img/write_io_bytes.png](img/write_io_bytes.png)
![img/write_bw.png](img/write_bw.png)
![img/read_io_kbytes.png](img/read_io_kbytes.png)
![img/write_iops_mean.png](img/write_iops_mean.png)


