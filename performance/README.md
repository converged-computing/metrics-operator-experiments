# Performance Experiments

This tree contains experiment setup and runs for testing across clouds.

 - [testing](testing): includes previous testing that isn't used for final experiments.
 - [docker](docker): docker builds that can be used across clouds. We are not using multi-stage builds, choosing redundancy in favor of being able to quickly rebuild or see the full picture, etc.
 - [google](google): Google Kubernetes Engine (minicluster setups)
 
## Plan

We will first need to know the maximize size of v100 we can get on GKE. We will then time and plan for a set of applicaitons (below) oriented to that. Then we will do the same for EKS and AKS. Currently, each minicluster setup is in a separate folder, but the final experiment will have one experiment run (with full instructions and configs for each application) in the same setup.
 
## Experiments

The following containers / setups are working (tested) on some size (and may need minor configuration figuring out) but largely need testing on a larger cluster size:

 - [google/multi-gpu-models](google/multi-gpu-models)
 - [google/lammps](google/lammps)
 - [google/kripke](google/kripke)
 - [google/resnet](google/resnet)
 - [google/amg2023](google/amg2023)
 - [google/quicksilver](google/quicksilver)
 - [google/laghos](google/laghos)
 - [google/minife](google/minife)
 - [google/stream](google/stream)
 - [google/mixbench](google/mixbench)
 - [google/nekrs5000](google/nekrs5000)
 - [google/osu](google/osu)
 - [google/mt-gem](google/mt-gem)

This one only has the sparse example working and needs more attention (likely a different example):

 - [google/magma](google/magma)


Next step is testing on a larger cluster.

### Not interested

- **pennant** is only useful for one node, one GPU (if we want that)
- **amgx** need to decide on problem to run and size (config, etc)
  - related to AMG?
- **hpc-benchmarks** for linpack we need to figure out how to run without infiniband (`--uxc-tls` or on a single node with at least 8 GPU). For hpcg (and others) we need to figure out the driver compatibility with V100. The 20.10 containers [here](https://catalog.ngc.nvidia.com/orgs/nvidia/containers/hpc-benchmarks/tags) ship with ubuntu 18.04, which is good for most but PMIX doesn't build.
- **deepspeed**: likely this won't work - Python libraries needed would be too old. Our best bet would be to use their container.
- **hpc-benchmarks hpcg/hpl** prepared a new container with basic build + download [from here](https://icl.utk.edu/hpcg/software/view.html?id=280)
