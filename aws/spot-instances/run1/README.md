# Spot Instances Experiments

We want to test LAMMPS performance (runtime, and MPItrace metrics) when we run on a managed node group
of spot instances. This experiment directory will include three approaches:

 - **test**: preparing for experiments (just small test runs to time different sizes primarily)
 - **region**: select from a region (but no placement group)
 - **placement group**: TBA
 - **fleet**: testing out AWS fleet (also TBA)

## Experiment Designs

Importantly, we want to ultimately test the ability of different machines types from spot to run LAMMPS, and not the result of the selection process itself. This decision drives the design below.

- For each of 20 batches:
  - Filter down the initial set to some number above a certain cost threshold
  - Randomly select 4 from that set AND give to the AWS API to create 8 nodes (this is flattened into one operation)
  - Then we have an instance group, 8 nodes for some unique set of instances from the set of 4
  - Run LAMMPS 20x, collect MPI trace too, lstopo and the AWS topology API

With the above we can calculate cost as:

```console
total cost = 20 batches x 1 selection of nodes x 20 runs x [TIME TO RUN EXPERIMENT] seconds
```

Also note that I've designed the experiments to have two managed node groups - one has just one node (small and inexpensive) to run the operators (and not go away) and the others are intended for spot. The CPU requirement for the spot is much higher than the operators so the jobs won't be scheduled on that node, but you could imagine putting other taints / etc. in place to more properly ensure that.

We will likely need to do some tests to estimate time to run for different sizes to properly prepare for this.
From Rajib we know that hpc7g (128 vCPU) were between 110-120 seconds, and hpc6a (192 vCPU) were 82-86 seconds. But I tested hpc7g earlier and it was much slower, so I think we probably need to do some new test runs.

### Environment

For the steps below (and experiments) you should install requirements.txt.

```bash
pip install -r requirements.txt
```

The [topology API](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2/client/describe_instance_topology.html) for aws is newer, so ensure you have the latest boto3:

```bash
pip install --upgrade boto3
```

Ideally from a virtual environment or similar. You'll also need this kubectl plugin:

```bash
curl -LO https://github.com/kvaps/kubectl-node-shell/raw/master/kubectl-node_shell
chmod +x ./kubectl-node_shell
sudo mv ./kubectl-node_shell /usr/local/bin/kubectl-node_shell
```

### Custom Resource Definitions

We will save hard copies of CRDs here for attempted reproducibility. Yes, the underlying containers might change (but we will do our best to be consistent)! Note that I tried to get versioned releases of each. Here is how this directory was generated:

```console
VERSION=v0.2.1
wget -O jobset-operator.yaml https://github.com/kubernetes-sigs/jobset/releases/download/$VERSION/manifests.yaml
wget https://github.com/converged-computing/metrics-operator/releases/download/0.1.13-1/metrics-operator.yaml
wget https://github.com/cert-manager/cert-manager/releases/download/v1.13.1/cert-manager.yaml
wget https://github.com/converged-computing/oras-operator/releases/download/0.0.11/oras-operator.yaml
```

These files can be used / shared between for the experiments here.

### Instance Selection

See [thinking process here](https://gist.github.com/vsoch/ad19f4270a0500a49c47008e4a853f62).

We want to (maybe) mimic the following instance types:

|Instance |Physical Cores | Memory (GiB) | EFA Network Bandwidth (Gbps) | Network Bandwidth (Gbps)* |
| hpc6a.48xlarge | 96vcpu  | 384 | 100 | 25 |
| hpc7g.16xlarge | 64vcpu | 128 | 200 | 25 |

Note that the main website says "physical cores" but other sites (e.g., [here](https://aws.amazon.com/ec2/pricing/on-demand/)) writes them as vCPU so I'm going to assume vCPU.  Our starting problem size is `64 x 16 x 16`.

## Estimating Cost

**Important** this relies on the [pull request branch here](https://github.com/converged-computing/cloud-select/pull/35). You can clone that and pip install.

The spot_instances.py can be used (and shared) between experiments to generate cost tables. To generate (don't run this if you already have an instances-aws.csv and it's recent.

```bash
python spot_instances.py gen
```

We need to find a cost that (divided by 3) is approximately 1k, which is our spending limit for these experiments, and assuming we do them for each of the cases described above. I first tried a range of cores (note updated from vCPU to be less confusing) we wanted to emulate:

### 64 cores

```bash
$ python spot_instances.py select --min-cores 64 --max-cores 64 --hypervisor nitro
```

Note that defaults to bare metal false. We aren't going to mix those. We also want to set the max price allowed to be what we would pay for hpc7g (which I don't remember, I'm going to just guess here).

<details>

<summary>Price estimation for 64 cores</summary>

```console
☝️  Max spot price: 8.625
👇️ Min spot price: 1.400025

😸️ Filtered selection of spot:
            instance  bare_metal    arch  vcpu  cores  threads_per_core  memory_mb hypervisor    gpu  spot_price     price
588     m7a.16xlarge       False  x86_64    64     64                 1     262144      nitro  False    1.400025   3.70944
624     c7a.16xlarge       False  x86_64    64     64                 1     131072      nitro  False    1.443750   3.28448
394     r7a.16xlarge       False  x86_64    64     64                 1     524288      nitro  False    2.357200   4.86880
208     c6a.32xlarge       False  x86_64   128     64                 2     262144      nitro  False    2.228020   4.89600
22      c6i.32xlarge       False  x86_64   128     64                 2     262144      nitro  False    2.490780   5.44000
206     m6a.32xlarge       False  x86_64   128     64                 2     524288      nitro  False    2.572120   5.52960
675    c6id.32xlarge       False  x86_64   128     64                 2     262144      nitro  False    2.625100   6.45120
236     m6i.32xlarge       False  x86_64   128     64                 2     524288      nitro  False    2.638740   6.14400
93      r6a.32xlarge       False  x86_64   128     64                 2    1048576      nitro  False    2.983180   7.25760
412    c6in.32xlarge       False  x86_64   128     64                 2     262144      nitro  False    3.168920   7.25760
40     m6id.32xlarge       False  x86_64   128     64                 2     524288      nitro  False    3.249800   7.59360
309     r6i.32xlarge       False  x86_64   128     64                 2    1048576      nitro  False    3.367380   8.06400
80     r6id.32xlarge       False  x86_64   128     64                 2    1048576      nitro  False    3.597560   9.67680
307     i4i.32xlarge       False  x86_64   128     64                 2    1048576      nitro  False    3.784500  10.98240
491    m6in.32xlarge       False  x86_64   128     64                 2     524288      nitro  False    3.930100   8.91072
519   m6idn.32xlarge       False  x86_64   128     64                 2     524288      nitro  False    4.015150  10.18368
369    r7iz.32xlarge       False  x86_64   128     64                 2    1048576      nitro  False    4.534225  11.90400
698   x2idn.32xlarge       False  x86_64   128     64                 2    2097152      nitro  False    4.706380  13.33800
605    r6in.32xlarge       False  x86_64   128     64                 2    1048576      nitro  False    5.135000  11.15712
602   r6idn.32xlarge       False  x86_64   128     64                 2    1048576      nitro  False    6.623075  12.50496
597    trn1.32xlarge       False  x86_64   128     64                 2     524288      nitro  False    6.712150  21.50000
552   trn1n.32xlarge       False  x86_64   128     64                 2     524288      nitro  False    7.939100  24.78000
278  x2iedn.32xlarge       False  x86_64   128     64                 2    4194304      nitro  False    8.625000  26.67600

🤓️ Mean (std) of spot price
$3.92 ($1.94)
```

</details>

### 96 cores

And then for 96. Note that these prices don't seem much better than the (on demand) hpc6a.

```bash
$ python spot_instances.py select --min-cores 96 --max-cores 96  --hypervisor nitro
```

<details>

<summary>Price estimation for 96 cores</summary>

```console
☝️  Max spot price: 5.22555
👇️ Min spot price: 1.8883

😸️ Filtered selection of spot:
          instance  bare_metal    arch  vcpu  cores  threads_per_core  memory_mb hypervisor    gpu  spot_price     price
571   c7a.24xlarge       False  x86_64    96     96                 1     196608      nitro  False    1.888300   4.92672
526   m7a.24xlarge       False  x86_64    96     96                 1     393216      nitro  False    2.418900   5.56416
202   r7a.24xlarge       False  x86_64    96     96                 1     786432      nitro  False    3.238600   7.30320
154   c6a.48xlarge       False  x86_64   192     96                 2     393216      nitro  False    3.246100   7.34400
31    m6a.48xlarge       False  x86_64   192     96                 2     786432      nitro  False    3.778100   8.29440
163   c7i.48xlarge       False  x86_64   192     96                 2     393216      nitro  False    3.967275   8.56800
4     m7i.48xlarge       False  x86_64   192     96                 2     786432      nitro  False    4.050275   9.67680
129   r6a.48xlarge       False  x86_64   192     96                 2    1572864      nitro  False    4.527040  10.88640
209  inf2.48xlarge       False  x86_64   192     96                 2     786432      nitro  False    4.869125  12.98127
461   r7i.48xlarge       False  x86_64   192     96                 2    1572864      nitro  False    5.225550  12.70080

🤓️ Mean (std) of spot price
$3.72 ($1.05)
```

</details>

I'm going to stop here for now, because I don't actually see a benefit in price as compared to the hpc instance family on demand.

 - hpc7g: 64 physical cores, $1.68 per hour
 - hpc6a: 96 physical cores, $2.88 per hour
