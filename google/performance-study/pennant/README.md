# Pennant Testing on Kubernetes

Containers for Pennant were prepared [here](https://github.com/converged-computing/metrics-containers/tree/main/pennant).
This would be an ideal testing cluster:

```bash
GOOGLE_PROJECT=myproject
gcloud container clusters create test-cluster --threads-per-core=1 --accelerator type=nvidia-tesla-a100,count=2 --num-nodes=1 --machine-type=a2-highgpu-2g --region=us-central1-a --project=${GOOGLE_PROJECT} 
```

But in practice we just asked for one:

```bash
gcloud container clusters create test-cluster --threads-per-core=1 --accelerator type=nvidia-tesla-a100,count=1 --num-nodes=1 --machine-type=a2-highgpu-1g --region=us-central1-a --project=${GOOGLE_PROJECT} 
```

We have to be sure the nodes have gpu. This is wrong:

```bash
$ kubectl get nodes gke-test-cluster-default-pool-c13c8eb0-sm0k -o json | jq .status.allocatable
```
```console
{
  "cpu": "5915m",
  "ephemeral-storage": "47060071478",
  "hugepages-1Gi": "0",
  "hugepages-2Mi": "0",
  "memory": "80404476Ki",
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
$ kubectl get nodes gke-test-cluster-default-pool-c13c8eb0-sm0k -o json | jq .status.allocatable
```
```console
{
  "cpu": "5915m",
  "ephemeral-storage": "47060071478",
  "hugepages-1Gi": "0",
  "hugepages-2Mi": "0",
  "memory": "80404476Ki",
  "nvidia.com/gpu": "1",
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

You can see the logs (and ensure the quorum is reached) and also get the path to the flux socket:

```bash
kubectl logs flux-sample-0-qdckd 
```
```console
🌀 flux broker --config-path /mnt/flux/view/etc/flux/config -Scron.directory=/etc/flux/system/cron.d   -Stbon.fanout=256   -Srundir=/mnt/flux/view/run/flux -Sbroker.rc2_none    -Sstatedir=/mnt/flux/view/var/lib/flux   -Slocal-uri=local:///mnt/flux/view/run/flux/local -Stbon.connect_timeout=5s    -Slog-stderr-level=6    -Slog-stderr-mode=local
broker.info[0]: start: none->join 0.653967ms
broker.info[0]: parent-none: join->init 0.023611ms
cron.info[0]: synchronizing cron tasks to event heartbeat.pulse
job-manager.info[0]: restart: 0 jobs
job-manager.info[0]: restart: 0 running jobs
job-manager.info[0]: restart: checkpoint.job-manager not found
broker.info[0]: rc1.0: running /etc/flux/rc1.d/01-sched-fluxion
sched-fluxion-resource.info[0]: version 0.33.1
sched-fluxion-resource.warning[0]: create_reader: allowlist unsupported
sched-fluxion-resource.info[0]: populate_resource_db: loaded resources from core's resource.acquire
sched-fluxion-qmanager.info[0]: version 0.33.1
broker.info[0]: rc1.0: running /etc/flux/rc1.d/02-cron
broker.info[0]: rc1.0: /etc/flux/rc1 Exited (rc=0) 0.4s
broker.info[0]: rc1-success: init->quorum 0.399801s
broker.info[0]: online: flux-sample-0 (ranks 0)
broker.info[0]: quorum-full: quorum->run 0.100596s
```

Notice in the above we have regenerated the resources.

```
```

I actually don't think we need flux installed in the container - the output of hwloc was the same to show the GPU as "3D" in both:

```bash
lstopo
```
```console
Machine (83GB total)
  Package L#0
    NUMANode L#0 (P#0 83GB)
    L3 L#0 (39MB)
      L2 L#0 (1024KB) + L1d L#0 (32KB) + L1i L#0 (32KB) + Core L#0 + PU L#0 (P#0)
      L2 L#1 (1024KB) + L1d L#1 (32KB) + L1i L#1 (32KB) + Core L#1 + PU L#1 (P#1)
      L2 L#2 (1024KB) + L1d L#2 (32KB) + L1i L#2 (32KB) + Core L#2 + PU L#2 (P#2)
      L2 L#3 (1024KB) + L1d L#3 (32KB) + L1i L#3 (32KB) + Core L#3 + PU L#3 (P#3)
      L2 L#4 (1024KB) + L1d L#4 (32KB) + L1i L#4 (32KB) + Core L#4 + PU L#4 (P#4)
      L2 L#5 (1024KB) + L1d L#5 (32KB) + L1i L#5 (32KB) + Core L#5 + PU L#5 (P#5)
  HostBridge
    PCI 00:03.0 (Other)
      Block "sda"
    PCI 00:04.0 (3D)
    PCI 00:05.0 (Ethernet)
    PCI 00:06.0 (Other)
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

Try running just pennant, and then a pennant job with flux.

```bash
pennant /opt/pennant/test/leblancbig/leblancbig.pnt
flux run -N 1 --gpus-per-node 1 pennant /opt/pennant/test/leblancbig/leblancbig.pnt
```

<details>

<summary>Pennant Output</summary>

```console
********************
Running PENNANT v0.6
********************

--- Mesh Information ---
Points:  232001
Zones:  230400
Sides:  921600
Edges:  462400
Side chunks:  1800
Point chunks:  454
Chunk size:  512
------------------------
Running Hydro on device...
End cycle      1, time = 1.00000e-03, dt = 1.00000e-03, wall = 8.84056e-04
dt limiter: Initial timestep
End cycle    100, time = 1.80646e-01, dt = 1.50494e-03, wall = 6.82290e-02
dt limiter: Hydro Courant limit for z =  76978
End cycle    200, time = 3.25140e-01, dt = 1.41462e-03, wall = 6.87139e-02
dt limiter: Hydro Courant limit for z =  76970
End cycle    300, time = 4.66173e-01, dt = 1.41272e-03, wall = 6.52530e-02
dt limiter: Hydro Courant limit for z =  77029
End cycle    400, time = 6.08548e-01, dt = 1.43732e-03, wall = 6.30610e-02
dt limiter: Hydro Courant limit for z =  76975
End cycle    500, time = 7.53605e-01, dt = 1.44100e-03, wall = 6.23090e-02
dt limiter: Hydro dV/V limit for z =  92905
End cycle    600, time = 9.00922e-01, dt = 1.51731e-03, wall = 6.23760e-02
dt limiter: Hydro Courant limit for z =  76960
End cycle    700, time = 1.04989e+00, dt = 1.46825e-03, wall = 6.23531e-02
dt limiter: Hydro dV/V limit for z =  99701
End cycle    800, time = 1.20029e+00, dt = 1.47909e-03, wall = 6.24018e-02
dt limiter: Hydro dV/V limit for z = 103200
End cycle    900, time = 1.35186e+00, dt = 1.57106e-03, wall = 6.24001e-02
dt limiter: Hydro dV/V limit for z = 106805
End cycle   1000, time = 1.50459e+00, dt = 1.52297e-03, wall = 6.23829e-02
dt limiter: Hydro dV/V limit for z = 110090
End cycle   1100, time = 1.65878e+00, dt = 1.50740e-03, wall = 6.24251e-02
dt limiter: Hydro dV/V limit for z = 113742
End cycle   1200, time = 1.81435e+00, dt = 1.58059e-03, wall = 6.25160e-02
dt limiter: Hydro dV/V limit for z = 117160
End cycle   1300, time = 1.97121e+00, dt = 1.59900e-03, wall = 6.23651e-02
dt limiter: Hydro dV/V limit for z = 120549
End cycle   1400, time = 2.12947e+00, dt = 1.54627e-03, wall = 6.24678e-02
dt limiter: Hydro dV/V limit for z = 124001
End cycle   1500, time = 2.28919e+00, dt = 1.59432e-03, wall = 6.25122e-02
dt limiter: Hydro dV/V limit for z = 127625
End cycle   1600, time = 2.45018e+00, dt = 1.69036e-03, wall = 6.24990e-02
dt limiter: Hydro dV/V limit for z = 130880
End cycle   1700, time = 2.61241e+00, dt = 1.59385e-03, wall = 6.27530e-02
dt limiter: Hydro dV/V limit for z = 134453
End cycle   1800, time = 2.77592e+00, dt = 1.61348e-03, wall = 6.24490e-02
dt limiter: Hydro dV/V limit for z = 137988
End cycle   1900, time = 2.93987e+00, dt = 1.66639e-03, wall = 6.24359e-02
dt limiter: Hydro Courant limit for z =  76970
End cycle   2000, time = 3.10357e+00, dt = 1.62783e-03, wall = 6.26550e-02
dt limiter: Hydro dV/V limit for z = 144800
End cycle   2100, time = 3.26634e+00, dt = 1.62155e-03, wall = 6.24301e-02
dt limiter: Hydro Courant limit for z =  77099
End cycle   2200, time = 3.42785e+00, dt = 1.61008e-03, wall = 6.22609e-02
dt limiter: Hydro Courant limit for z =  77098
End cycle   2300, time = 3.58862e+00, dt = 1.60654e-03, wall = 6.22561e-02
dt limiter: Hydro Courant limit for z =  77020
End cycle   2400, time = 3.74939e+00, dt = 1.60994e-03, wall = 6.22101e-02
dt limiter: Hydro Courant limit for z =  76962
End cycle   2500, time = 3.91079e+00, dt = 1.61879e-03, wall = 6.22239e-02
dt limiter: Hydro Courant limit for z =  76960
End cycle   2600, time = 4.07328e+00, dt = 1.63143e-03, wall = 6.21641e-02
dt limiter: Hydro Courant limit for z =  76960
End cycle   2700, time = 4.23716e+00, dt = 1.64613e-03, wall = 6.21948e-02
dt limiter: Hydro Courant limit for z =  76964
End cycle   2800, time = 4.40243e+00, dt = 1.66115e-03, wall = 6.21972e-02
dt limiter: Hydro Courant limit for z =  76960
End cycle   2900, time = 4.56860e+00, dt = 1.64787e-03, wall = 6.21898e-02
dt limiter: Hydro dV/V limit for z = 174919
End cycle   3000, time = 4.73514e+00, dt = 1.68444e-03, wall = 6.20892e-02
dt limiter: Hydro Courant limit for z =  76960
End cycle   3100, time = 4.90158e+00, dt = 1.65632e-03, wall = 6.20549e-02
dt limiter: Hydro dV/V limit for z = 181877
End cycle   3200, time = 5.06734e+00, dt = 1.66808e-03, wall = 6.20370e-02
dt limiter: Hydro dV/V limit for z = 185250
End cycle   3300, time = 5.23224e+00, dt = 1.61447e-03, wall = 6.20470e-02
dt limiter: Hydro dV/V limit for z = 188787
End cycle   3400, time = 5.39603e+00, dt = 1.67547e-03, wall = 6.20601e-02
dt limiter: Hydro Courant limit for z =  77099
End cycle   3500, time = 5.55863e+00, dt = 1.58314e-03, wall = 6.22039e-02
dt limiter: Hydro dV/V limit for z = 195571
End cycle   3600, time = 5.72027e+00, dt = 1.63621e-03, wall = 6.26681e-02
dt limiter: Hydro dV/V limit for z = 199113
End cycle   3700, time = 5.88090e+00, dt = 1.59163e-03, wall = 6.22149e-02
dt limiter: Hydro dV/V limit for z = 202415

Run complete
cycle =   3775,         cstop = 999999
time  =   6.000000e+00, tstop =   6.000000e+00
```

</details>

You can of course adjust parameters to change the runtime.  Here is an asciinema of the first run!

[![asciicast](https://asciinema.org/a/656639.svg)](https://asciinema.org/a/656639?speed=2)

Have fun!

## Experiment Planning

We want to do:

- ideal: 8 gpu per node, 32 nodes
- minimum: 4 gpu per node, 64 nodes
- ideally a100, second choice v100 (which instance type)?


### Clean Up

When you are done:

```bash
gcloud container clusters delete test-cluster --region=us-central1-a
```
