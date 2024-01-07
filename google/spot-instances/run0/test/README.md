# Spot Instance Experiment Test

We want to test LAMMPS performance (runtime, and MPItrace metrics) when we run on a managed node group
of spot instances. This is a test experiment directory to prototype the overall design, and test different sizes (and get estimated times). To see the design, see the higher level [README](../). Our primary interest here is to calculate cost for different sizes.

We were going to test the following sizes:

 - 96 vCPU x 8
 - 64 vCPU x 8
 - 128 cores x 6 (to mimic 768 cores)

How nice that Google Cloud has a flag to ask for one thread per core? Ahh, relief!

## Experiment Plan

You can see the experiment plans in the top of [run-experiment.py](run-experiment.py). They have keys that correspond to the config name, and provide variables that go into templates via Jinja2.

### lammps

This section includes template subs for the metrics.yaml file in [metrics](metrics). This makes it easy to ensure that we have specific parameters for each vCPU size. And no, we aren't writing a new workflow / templating thing!

## Environment

For the steps below (and experiments) you should install requirements.txt.

```bash
pip install -r ../requirements.txt
```

Ideally from a virtual environment or similar.

## Usage

Ensure you have created a GitHub PAT with push/pull (read/write) for GitHub packages. Then
export credentials:

```bash
export ORAS_USER=mygithub
export ORAS_PASS=xxxxxxxxxxxxx
```

Then run the script. The defaults should be set for this testing, but we can set them to be extra careful.

```console
Spot Instance Experiment Running

options:
  -h, --help            show this help message and exit
  --data-dir DATA_DIR   path to save data
  -n NAME, --name NAME  select one or more experiments by name
  --zone ZONE           Zone to request resources for (e.g., us-central1-a).
  --region REGION       Region to request resources for (e.g., us-central1). Be careful, as this often means getting them across zones.
  --iters ITERS         iterations of lammps to run per cluster (set to 1 for testing)
  --batches BATCHES     batches (number of selections of instance types) for one subset (set to 1 for testing)
  --sleep SLEEP         seconds to sleep to allow for container pulls
  --has-gpu             select GPU instances
  --cluster-name CLUSTER_NAME
                        cluster name to use (defaults to spot-instance-testing-cluster
  --project PROJECT     Google cloud project name
  --machine-type MACHINE_TYPE
                        machine type for single 'sticky' node to install operators to.
  --nodes NODES         number of spot instances (and nodes) to request.
  --max-vcpu MAX_VCPU   Max vcpu ONLY for the sticky (single) operator node
  --max-memory MAX_MEMORY
                        Max memory ONLY for the sticky (single) operator node
```

Here was a testing run. Note that we are selecting the experiment by `--name`. The machine type here
is for our "sticky node" that we will install operators to.

```bash
python run-experiment.py --nodes 4 --iters 1 --name 4x32vcpu --project llnl-flux --machine-type c2d-standard-16 --zone us-central1-a
```
```console
🧪️ Planning experiments for {'cores': 16, 'name': '4x32vcpu', 'filter-instance-types': 20, 'max-spot-price': 2, 'lammps': {'cpu': 10, 'x': 2, 'y': 2, 'z': 2, 'np': 16}}

☝️  Max spot price: 0.5775879224109589
👇️ Min spot price: 0.1657653304109589

😸️ Filtered selection of spot:
            instance  vcpu  cores  memory_mb    gpu  spot_price     price
8     c2d-highcpu-32    32   16.0      65536  False    0.165765  1.387036
22   c2d-standard-32    32   16.0     131072  False    0.201155  1.685553
83     e2-highcpu-32    32   16.0      32768  False    0.239227  0.794865
15    c2d-highmem-32    32   16.0     262144  False    0.271934  2.282586
109    n2-highcpu-32    32   16.0      32768  False    0.313117  1.325582
95    e2-standard-32    32   16.0     131072  False    0.325445  1.082260
129   n2-standard-32    32   16.0     131072  False    0.426462  2.264385
119    n2-highmem-32    32   16.0     262144  False    0.577588  3.516123

🤓️ Mean (std) of spot price
$0.32 ($0.13)

🧪️ Experiments:
   4x32vcpu
🪴️ Planning to run:
   Cluster name        : spot-instance-testing-cluster
     location          : us-central1-a
   Output Data         : /home/vanessa/Desktop/Code/metrics-operator-experiments/google/spot-instances/run0/test/data
   Experiments         : 1
     nodes             : 4
   Batches             : 1
     iterations/batch  : 1
Would you like to continue? (yes/no)? 
```

Stopped here - note that the e* family of instances absolutely don't work. Likely for my next step I need to go through the instance types and see which actually run for a small problem size, and intelligently filter from there.
