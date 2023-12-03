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

- It would be ideal to not have to manually disable hyper-threading. I've [posted to AWS about this](https://github.com/aws/containers-roadmap/issues/2225) and am aware eksctl can run a step at boot (that might be useful for a future experiment setup). I also think we would be better off having one node that is explicitly for operators. E.g., if we lose our spot instance that has the operators installed, we have to re-install (and that's not great).  That will add additional complexity, but if/when we go that route we will need to:
- I think as we increase the size of a spot job, there will be a higher chance of failure (since one job == failure). E.g., 4 spot nodes are more likely to be successful than 8.

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
Here was a testing run. Note that we are selecting the experiment by `--name`

```bash
python run-experiment.py --nodes 4 --keypair-name spot-node-test --keypair-file ./spot-node-test.pem --iters 10 --name 4x32vcpu
```

The above was too small to be something we actually wanted to run! Here are the experiment sizes we were interested in. I separated them out so each has its own results, but that isn't necessary (e.g,. you can provide `--name` more than once).


```bash
python run-experiment.py --nodes 4 --keypair-name spot-node-test --keypair-file ./spot-node-test.pem --iters 10 --name 4x32vcpu
```


### Post Processing

Here is what the experiment will look like finishing up.

```console
🥞️ Attempting delete of node group spot-instance-testing-cluster-worker-group...
Node group spot-instance-testing-cluster-worker-group is deleted successfully
Experiments are done! Next, use ORAS to pull artifacts.
🥞️ Attempting delete of node group sticky-node...
Node group sticky-node is deleted successfully
🥞️ Attempting delete of node group spot-instance-testing-cluster-worker-group...
✖️  Node Group spot-instance-testing-cluster-worker-group does not exist.
⏳️ Cluster deletion started! Waiting...
🥅️ Deleting VPC and associated assets...
🥞️ Attempting delete of stack spot-instance-testing-cluster-vpc...
⭐️ Done!
total time to run is 2286.7317328453064 seconds
```

If you are lucky (?) I suspect this means not losing a node in the middle of the run, it will
finish without issue. And then to download oras results (with your credentials):

```
mkdir -p ./data/4x32vcpu
# Here is just an example
for tag in $(oras repo tags -u $ORAS_USER -p $ORAS_PASS ghcr.io/manbat/metrics-operator-results); do
   mkdir -p ${tag}
   cd ${tag}
   oras pull -u $ORAS_USER -p $ORAS_PASS ghcr.io/manbat/metrics-operator-results:${tag} ${tag}.tar.gz
   tar -xzvf ${tag}
   cd -
done
```

Note that we will want to create a directory for each tag, and to extract there. The result has
MPI trace and lammps log and hwloc! I just extracted one of each as an example.

