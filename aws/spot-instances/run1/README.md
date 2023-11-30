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

We will likely need to do some tests to estimate time to run for different sizes to properly prepare for this.
From Rajib we know that hpc7g (128 vCPU) were between 110-120 seconds, and hpc6a (192 vCPU) were 82-86 seconds. But I tested hpc7g earlier and it was much slower, so I think we probably need to do some new test runs.

### Environment

For the steps below (and experiments) you should install requirements.txt.

```bash
pip install -r requirements.txt
```

Ideally from a virtual environment or similar.

### Instance Selection

See [thinking process here](https://gist.github.com/vsoch/ad19f4270a0500a49c47008e4a853f62).

We want to (maybe) mimic the following instance types:

|Instance |Physical Cores | Memory (GiB) | EFA Network Bandwidth (Gbps) | Network Bandwidth (Gbps)* |
| hpc6a.48xlarge | 96 (192 vCPU) | 384 | 100 | 25 |
| hpc7g.16xlarge | 64 (128 vCPU) | 128 | 200 | 25 |

Note that the website says "physical cores" so that means we need to search for 96x2 == 192 vCPU.
Our starting problem size is `64 x 16 x 16`.

## Estimating Cost

**Important** this relies on the [pull request branch here](https://github.com/converged-computing/cloud-select/pull/35). You can clone that and pip install.

The spot_instances.py can be used (and shared) between experiments to generate cost tables. To generate (don't run this if you already have an instances-aws.csv and it's recent.

```bash
python spot_instances.py gen
```

### 128 vCPU

We need to find a cost that (divided by 3) is approximately 1k, which is our spending limit for these experiments, and assuming we do them for each of the cases described above. I first tried a range of vCPU we wanted to emulate:

```bash
$ python spot_instances.py select --min-vcpu 128 --max-vcpu 128 --number 20
```

Note that defaults to bare metal false. We aren't going to mix those.

<details>

<summary>Price estimation for 128 vCPU</summary>

```bash
$ python spot_instances.py select --min-vcpu 128 --max-vcpu 128 --number 20
```
```console
Selected subset table:
           instance  bare_metal    arch  vcpu  threads_per_core  memory_mb    gpu  spot_price     price
465    c6a.32xlarge       False  x86_64   128                 2     262144  False    2.201160   4.89600
211    c7a.32xlarge       False  x86_64   128                 1     262144  False    2.323425   6.56896
691    c6i.32xlarge       False  x86_64   128                 2     262144  False    2.478600   5.44000
248    m6a.32xlarge       False  x86_64   128                 2     524288  False    2.628120   5.52960
209    m6i.32xlarge       False  x86_64   128                 2     524288  False    2.676000   6.14400
343   c6id.32xlarge       False  x86_64   128                 2     262144  False    2.687360   6.45120
298    r6a.32xlarge       False  x86_64   128                 2    1048576  False    2.930780   7.25760
1      m7a.32xlarge       False  x86_64   128                 1     524288  False    3.117800   7.41888
273   c6in.32xlarge       False  x86_64   128                 2     262144  False    3.239400   7.25760
193   m6id.32xlarge       False  x86_64   128                 2     524288  False    3.303780   7.59360
359    r6i.32xlarge       False  x86_64   128                 2    1048576  False    3.371040   8.06400
203   r6id.32xlarge       False  x86_64   128                 2    1048576  False    3.631980   9.67680
718    i4i.32xlarge       False  x86_64   128                 2    1048576  False    3.704200  10.98240
335    r7a.32xlarge       False  x86_64   128                 1    1048576  False    3.727750   9.73760
685  m6idn.32xlarge       False  x86_64   128                 2     524288  False    3.984450  10.18368
431   m6in.32xlarge       False  x86_64   128                 2     524288  False    4.009550   8.91072
316     x1.32xlarge       False  x86_64   128                 2    1998848  False    4.393550  13.33800
213   r7iz.32xlarge       False  x86_64   128                 2    1048576  False    4.446850  11.90400
39   x2idn.32xlarge       False  x86_64   128                 2    2097152  False    4.623940  13.33800
4     r6in.32xlarge       False  x86_64   128                 2    1048576  False    5.122650  11.15712

😸️ Final selection of spot:
c6a.32xlarge
c7a.32xlarge
c6i.32xlarge
m6a.32xlarge
m6i.32xlarge
c6id.32xlarge
r6a.32xlarge
m7a.32xlarge
c6in.32xlarge
m6id.32xlarge
r6i.32xlarge
r6id.32xlarge
i4i.32xlarge
r7a.32xlarge
m6idn.32xlarge
m6in.32xlarge
x1.32xlarge
r7iz.32xlarge
x2idn.32xlarge
r6in.32xlarge

🤓️ Mean (std) of price
$3.43 ($0.82)
```

</details>

### 192 vCPU

I think likely we can't do this size because there aren't a ton of instances to choose from.

<details>

<summary>Price estimation for 128 vCPU</summary>

```bash
$ python spot_instances.py select --min-vcpu 192 --max-vcpu 192 --number 20
```
```console
Selected subset table:
          instance  bare_metal    arch  vcpu  threads_per_core  memory_mb    gpu  spot_price     price
581   c6a.48xlarge       False  x86_64   192                 2     393216  False    3.207520   7.34400
381   c7a.48xlarge       False  x86_64   192                 1     393216  False    3.671550   9.85344
152   m6a.48xlarge       False  x86_64   192                 2     786432  False    3.735820   8.29440
689   c7i.48xlarge       False  x86_64   192                 2     393216  False    3.948450   8.56800
698   m7i.48xlarge       False  x86_64   192                 2     786432  False    4.011800   9.67680
150   r6a.48xlarge       False  x86_64   192                 2    1572864  False    4.505600  10.88640
566   r7i.48xlarge       False  x86_64   192                 2    1572864  False    4.588400  12.70080
449   m7a.48xlarge       False  x86_64   192                 1     786432  False    4.720575  11.12832
238  inf2.48xlarge       False  x86_64   192                 2     786432  False    4.758775  12.98127
712   r7a.48xlarge       False  x86_64   192                 1    1572864  False    6.843625  14.60640

😸️ Final selection of spot:
c6a.48xlarge
c7a.48xlarge
m6a.48xlarge
c7i.48xlarge
m7i.48xlarge
r6a.48xlarge
r7i.48xlarge
m7a.48xlarge
inf2.48xlarge
r7a.48xlarge

🤓️ Mean (std) of price
$4.4 ($1.0)
```

### 64 vCPU

What if we try closer to what we did on Google Cloud, closer to 50 vCPU. It looks like the closest we can get is 64 vCPU. A size 64 vCPU is fairly good, because we might have 32 actual CPU per node.

```bash
$ python spot_instances.py select --min-vcpu 64 --max-vcpu 64 --number 20
```

<details>

<summary>Price estimation for 128 vCPU</summary>

```console
Selected subset table:
          instance  bare_metal    arch  vcpu  threads_per_core  memory_mb    gpu  spot_price    price
679   c6a.16xlarge       False  x86_64    64                 2     131072  False    1.151780  2.44800
212  c5ad.16xlarge       False  x86_64    64                 2     131072  False    1.163000  2.75200
729   c5a.16xlarge       False  x86_64    64                 2     131072  False    1.210240  2.46400
10    m5a.16xlarge       False  x86_64    64                 2     262144  False    1.314160  2.75200
474   c6i.16xlarge       False  x86_64    64                 2     131072  False    1.325060  2.72000
25    m6a.16xlarge       False  x86_64    64                 2     262144  False    1.364100  2.76480
515    m5.16xlarge       False  x86_64    64                 2     262144  False    1.369840  3.07200
234  c6id.16xlarge       False  x86_64    64                 2     131072  False    1.380580  3.22560
671   c7i.16xlarge       False  x86_64    64                 2     131072  False    1.394750  2.85600
402    m4.16xlarge       False  x86_64    64                 2     262144  False    1.398133  3.20000
354   m7a.16xlarge       False  x86_64    64                 1     262144  False    1.403450  3.70944
291   c7a.16xlarge       False  x86_64    64                 1     131072  False    1.411625  3.28448
221   r5a.16xlarge       False  x86_64    64                 2     524288  False    1.511780  3.61600
635   m6i.16xlarge       False  x86_64    64                 2     262144  False    1.515600  3.07200
153   r6i.16xlarge       False  x86_64    64                 2     524288  False    1.515940  4.03200
525   r6a.16xlarge       False  x86_64    64                 2     524288  False    1.544920  3.62880
347   m7i.16xlarge       False  x86_64    64                 2     262144  False    1.587725  3.22560
27    m5d.16xlarge       False  x86_64    64                 2     262144  False    1.603920  3.61600
720  m5ad.16xlarge       False  x86_64    64                 2     262144  False    1.615520  3.29600
721  m6id.16xlarge       False  x86_64    64                 2     262144  False    1.615700  3.79680

😸️ Final selection of spot:
c6a.16xlarge
c5ad.16xlarge
c5a.16xlarge
m5a.16xlarge
c6i.16xlarge
m6a.16xlarge
m5.16xlarge
c6id.16xlarge
c7i.16xlarge
m4.16xlarge
m7a.16xlarge
c7a.16xlarge
r5a.16xlarge
m6i.16xlarge
r6i.16xlarge
r6a.16xlarge
m7i.16xlarge
m5d.16xlarge
m5ad.16xlarge
m6id.16xlarge

🤓️ Mean (std) of price
$1.42 ($0.14)
```

</details>

That also gives us many choices under $2, so I am leaning toward this as our choice (but need to test timing and problem sizes).
