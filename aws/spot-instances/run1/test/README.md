# Spot Instance Experiment Test

We want to test LAMMPS performance (runtime, and MPItrace metrics) when we run on a managed node group
of spot instances. This is a test experiment directory to prototype the overall design, and test different sizes (and get estimated times). To see the design, see the higher level [README](../). Our primary interest here is to calculate cost
for different sizes, namely, the cost below should be approximately 1/3 of 1k.

```console
total cost = 20 batches x 1 selection of nodes x 20 runs x [TIME TO RUN EXPERIMENT] seconds
```

We are going to test the following sizes:

 - 128 vCPU
 - 192 vCPU
 - 64 vCPU

## Notes from V

It would be ideal to not have to manually disable hyper-threading. I've [posted to AWS about this]() and am aware eksctl can run a step at boot (that might be useful for a future experiment setup). I also think we would be better off having one node that is explicitly for operators. E.g., if we lose our spot instance that has the operators installed, we have to re-install (and that's not great).  That will add additional complexity, but if/when we go that route we will need to:

## Experiment Plan

This is what the basic design for an experiment plan looks like:

```python
experiment_plans = [
    {"vcpu": 64, "max-instance-types": 4, "filter-instance-types": 20},
    {"vcpu": 128, "max-instance-types": 4, "filter-instance-types": 20},
    {"vcpu": 192, "max-instance-types": 4, "filter-instance-types": 20},
]
```

and when we add LAMMPS variables:

```
experiment_plans = [
    {
        "vcpu": 32,
        "max-instance-types": 4,
        "filter-instance-types": 20,
        # Subs / variables for this problem size.
        # We aren't setting memory because all the spot instances are different
        "lammps": {
            "[[CPU]]": 10,
            "[[X]]": 2,
            "[[Y]]": 2,
            "[[Z]]": 2,
            "[[NP]]": 16,
        },
    },
]
```

and specifically:

### filter-instance-types

The number to filter down to (after being sorted by spot instance prices, low to high).

### max-instance-types

The max number of instance types to ultimately select from the filtered set.
This is a balance between "If we allow too many, more likely to get same ones" vs. "If we ask for too few, unlikely to get an allocation."

Note that the number of nodes is set as a script argument `--nodes` and defaults to 8. In practice we add one more node to allow some extra resources to install the operator to. Each resource request/limit will still need to be tweaked to ensure assignment of one lammps pod / physical node.

### lammps

This section includes template subs for the metrics.yaml file in [metrics](metrics). This makes it easy to ensure that we have
specific parameters for each vCPU size. And no, we aren't writing a new workflow / templating thing!

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
usage: run-experiment.py [-h] [--data-dir DATA_DIR] [--iters ITERS] [--batches BATCHES] [--sleep SLEEP]
                         [--hypervisor HYPERVISOR] [--keypair-file KEYPAIR_FILE] [--keypair-name KEYPAIR_NAME]
                         [--bare-metal] [--has-gpu] [--cluster-name CLUSTER_NAME] [--arch ARCH] [--nodes NODES]

Spot Instance Experiment Running

options:
  -h, --help            show this help message and exit
  --data-dir DATA_DIR   path to save data
  --iters ITERS         iterations of lammps to run per cluster (set to 1 for testing)
  --batches BATCHES     batches (number of selections of instance types) for one subset (set to 1 for testing)
  --sleep SLEEP         seconds to sleep to allow for container pulls
  --hypervisor HYPERVISOR
                        filter to this hypervisor
  --keypair-file KEYPAIR_FILE
                        keypair file to create or use (required)
  --keypair-name KEYPAIR_NAME
                        keypair name to create or use (required)
  --bare-metal          select bare metal instances
  --has-gpu             select GPU instances
  --cluster-name CLUSTER_NAME
                        cluster name to use (defaults to spot-instance-testing-cluster
  --arch ARCH           architecture to select (defaults to x86_64
  --nodes NODES         number of spot instances (and nodes) to request.
```

Note that most metal instances are filtered out per threading.
Here was a testing run:

```bash
python run-experiment.py --nodes 4 --keypair-name spot-node-test --keypair-file ./spot-node-test.pem
```
