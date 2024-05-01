# Performance Experiments

This tree contains experiment setup and runs for testing across clouds.

 - [testing](testing): includes previous testing that isn't used for final experiments.
 - [docker](docker): docker builds that can be used across clouds. We are not using multi-stage builds, choosing redundancy in favor of being able to quickly rebuild or see the full picture, etc.
 - [google](google): Google Kubernetes Engine (minicluster setups)
 
## Plan

We will first need to know the maximize size of v100 we can get on GKE. We will then time and plan for a set of applicaitons (below) oriented to that. Then we will do the same for EKS and AKS. Currently, each minicluster setup is in a separate folder, but the final experiment will have one experiment run (with full instructions and configs for each application) in the same setup.
 
## Experiments

The following containers / setups are working (tested) on some size (and may need minor configuration figuring out):

 - [google/amgx](google/amgx)
 - [google/pennant](google/pennant): Can be run on a100 or v100, but only with one node and GPU.
 - [google/multi-gpu-models](google/multi-gpu-models)

### Next Hackathon Tasks

For the next hackathon, my goal is to get as far with each container and minicluster setup as possible. Ideally I will have a mostly working container that needs some debugging. Here are notes for each - for this first set, the container has been tested alongside 4 GPU x 2 nodes.

- **multi-gpu-models** needs testing on largest size to get slowest time, then do ETA for experiments
- **amgx** need to decide on problem to run and size (config, etc)
- **pennant** is only useful for one node, one GPU (if we want that)
- **hpc-benchmarks** for linpack we need to figure out how to run without infiniband (`--uxc-tls` or on a single node with at least 8 GPU). For hpcg (and others) we need to figure out the driver compatibility with V100. The 20.10 containers [here](https://catalog.ngc.nvidia.com/orgs/nvidia/containers/hpc-benchmarks/tags) ship with ubuntu 18.04, which is good for most but PMIX doesn't build.
- **lammps** (two variants): lammps runs but there is an error message (appears before) that needs looking into.
- **kripke**: needs a new container built - the one that built and works doesn't work on the GPUs.
- **mixbench**: the cu file is not compatible, likely needs a tweak and rebuild.
- **nek5000**: seems to work! But GPU utilization goes down - need to decide on what/how to run it.
- **osu**: the point to point seems to work OK, not sure if all_reduce (or any collective) is a thing. I think we are supposed to use NCCL?
- **mt-gem**: runs successfully on 2 nodes, 8 GPU, about 28 seconds.

For this next set, the container is built but needs another cluster creation for testing.

- **deepspeed**: likely this won't work - Python libraries needed would be too old. Our best bet would be to use their container.
- **hpc-benchmarks hpcg/hpl** prepared a new container with basic build + download [from here](https://icl.utk.edu/hpcg/software/view.html?id=280)
