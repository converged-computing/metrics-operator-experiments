# Spot Instances with Equivalent vCPU

> The Potpourri approach! But seriously, don't eat it.

Based on [these experiments](https://github.com/converged-computing/cloud-select/tree/main/examples/spot-instances/experiments/request-success) I want to naively try running lammps, first with the simplest approach (no Flux) that just runs across nodes with mpirun. The idea is that if we can get a spot instance allocation with different instance types we can always add on different instances with that same type. I'm going to test this by
creating several instances with the same amount of CPU via a managed node group, installing the metrics operator on them, and then trying to run the "same" lammps run and timing it / seeing if it works. If we want dynamic scaling we likely need to add Flux after this.

## Estimating Cost

A size 32 vCPU is fairly good, because we might have 16 actual CPU per node (for a small problem size?).
The below says "give me 10 instance types that have exactly 32vcpu"

```
Selected subset table:
         instance  bare_metal    arch  vcpu  threads_per_core  memory_mb    gpu    price
333  r6in.8xlarge       False  x86_64    32                 2     262144  False  1.47200
592   c7i.8xlarge       False  x86_64    32                 2      65536  False  1.47200
483  c5ad.8xlarge       False  x86_64    32                 2      65536  False  1.54100
159   m6a.8xlarge       False  x86_64    32                 2     131072  False  1.64564
727  c6id.8xlarge       False  x86_64    32                 2      65536  False  1.66880
636   c6a.8xlarge       False  x86_64    32                 2      65536  False  1.76480
351  m5ad.8xlarge       False  x86_64    32                 2     131072  False  1.80300
513    h1.8xlarge       False  x86_64    32                 2     131072  False  1.87200
90   inf2.8xlarge       False  x86_64    32                 2     131072  False  1.96786
416   r5a.8xlarge       False  x86_64    32                 2     262144  False  1.97200

😸️ Final selection of spot:
r6in.8xlarge
c7i.8xlarge
c5ad.8xlarge
m6a.8xlarge
c6id.8xlarge
c6a.8xlarge
m5ad.8xlarge
h1.8xlarge
inf2.8xlarge
r5a.8xlarge

🤓️ Mean (std) of price
$1.72 ($0.19)
```

So if we have 8 nodes at an hour each, that would be 1.72 * 8 == ~14.00 (rounded up). That seems like an OK testing size!

## Experiment

### Planning

What you should do to run an experiment:

 - Make a basic "plan" in the [plans](plans) folder. It mostly just needs the vCPU.
 - Look at the templates at the top of the [run-experiment.py](run-experiment.py) and ensure that the lammps  and hwloc template specs look okay.
 - Decide your parameters and then proceed to the next section!

For the last point, as an example you likely want to change the problem size depending on your parameters. We could put this as a variable somewhere.
It's intended to be small for just testing (I tried to not use too much money).

### Notes

Some important notes:

 - You likely want to change the size of the lammps run in the `lammps_template`
 - The timeout for waiting is 10 minutes for a nodgroup, and you can customize that.
 - If you want to record the timeout we currently don't do that (we just continue)
 - Lammps by default waits 10 seconds (sleep) for the network. This might need to be upped for larger clusters / if the network isnt' great. Ping V if we need to [expose that as a variable](https://github.com/converged-computing/metrics-operator/blob/960fcc48248c3a9b26844194e5b11b5c1e16b76a/pkg/metrics/launcher.go#L181-L182)

### Running 

The command below says "Try to get 8 nodes using a request range of 6-10 spot instance types selecting from a group of 10" and for that, we will run LAMMPS 2 times. This (in practice) will be two clusters.

```bash
# I did this out of caution, not sure if it's needed given I specify it
export KUBECONFIG=./kubeconfig-aws.yaml
python run-experiment.py --cluster-name cluster-8-32vcpu --max-instance-types 10 --min-spot-request 6 --max-spot-request 10 --nodes 8 --plan ./plans/32vcpu.json --data-dir ./data --iters 2
```

**Important** I've chosen a larger range anticipating we can get an allocation. If you lower the number (e.g., to 2 or 3) depending on the selection you might not get the allocation. The script currently does not do any kind of timeout so you will be waiting forever :) The assumption here is that we _want_ to test a large range of instances, so we don't want to ask for a small number.

In practice, we don't know how the spot algorithm works. In testing I saw sometimes getting more than one machine type, and other times just one. I suspect AWS takes our list and tries to give us the first one, and up to the max they have. We can likely check this. It could be we ask for 8 but are given all of one type. We will find out.
Here is a quick way to inspect node output and see which types were used:

```bash
$ cat nodes-8-request-count-6.json |grep node.kubernetes.io/instance-type | uniq
                    "node.kubernetes.io/instance-type": "r5a.8xlarge",
                    "node.kubernetes.io/instance-type": "c7i.8xlarge",
```

Note that if we see huge differences in time (based on instance types) then we can add in hwloc. We will need to get the unique node types, and then run the metric on all nodes (but only save for a subset that are the unique types so we don't have too much data). Note that locally you can also watch what is going on by using the kubeconfig:

```bash
KUBECONFIG=./kubeconfig-aws.yaml kubectl get pods 
```

I will be running this through, once fully, to get a test result and then I think it's ready for more use.

### Plot Results

Maybe... maybe... maybe?
