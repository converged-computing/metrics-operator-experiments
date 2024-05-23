# Performance Experiments

This tree contains experiment setup and runs for testing across clouds.

 - [testing](testing): includes previous testing that isn't used for final experiments.
 - [docker](docker): docker builds that can be used across clouds. We are not using multi-stage builds, choosing redundancy in favor of being able to quickly rebuild or see the full picture, etc.
 - [google](google): Google Kubernetes Engine (minicluster setups)

## Containers

Since we need to vary builds across clouds, let's keep track of that here. These only include the ones we are intending to run.

| Container                                                      | Cloud     | GPU | Dockerfile                          | Notes             |
|----------------------------------------------------------------|-----------|-----|------------------------------------|--------------------|
| ghcr.io/converged-computing/metric-amg2023:spack-slim          | Google    | yes |[Dockerfile](docker/google/amg2023) | Using slim variant |
| ghcr.io/converged-computing/metric-kripke-gpu:latest           | Google    | yes |[Dockerfile](docker/google/kripke)  | |
| ghcr.io/converged-computing/metric-laghos:gpu                  | Google    | yes |[Dockerfile](docker/google/laghos)  | Needs to be built on large machine  |
| ghcr.io/converged-computing/metric-lammps-gpu:kokkos           | Google    | yes |[Dockerfile](docker/google/lammps)  | using Kokkos build |
| ghcr.io/converged-computing/metric-magma                       | Google    | yes |[Dockerfile](docker/google/magma)   |  |
| ghcr.io/converged-computing/metric-minife:latest               | Google    | yes |[Dockerfile](docker/google/minife)  | | 
| ghcr.io/converged-computing/metric-mixbench:latest             | Google    | yes |[Dockerfile](docker/google/mixbench)| |
| ghcr.io/converged-computing/mt-gemm:latest                     | Google    | yes |[Dockerfile](docker/google/mt-gemm-base)| |
| ghcr.io/converged-computing/multi-gpu-models:flux-gpu          | Google    | yes |[Dockerfile](docker/google/multi-gpu-models)| |
| ghcr.io/converged-computing/metric-nek5000:latest              | Google    | yes |[Dockerfile](docker/google/nek5000) | |
| ghcr.io/converged-computing/metric-osu-gpu:latest              | Google    | yes |[Dockerfile](docker/google/osu) | |
| ghcr.io/converged-computing/metric-quicksilver-gpu:latest      | Google    | yes |[Dockerfile](docker/google/quicksilver) | |
| ghcr.io/converged-computing/pytorch-resnet-experiment:gpu      | Google    | yes |[Dockerfile](docker/google/resnet) | |
| ghcr.io/converged-computing/metric-stream:latest               | Google    | yes |[Dockerfile](docker/google/stream) | | 
| ghcr.io/converged-computing/metric-amg2023:spack-slim     | AWS    | yes |[Dockerfile](docker/google/amg2023) | Same as Google, already has libfabric |
| ghcr.io/converged-computing/metric-lammps-gpu:libfabric   | AWS | yes |[Dockerfile](docker/aws/lammps) | |
| ghcr.io/converged-computing/metric-kripke-gpu:libfabric   | AWS | yes |[Dockerfile](docker/aws/kripke)  | |
| ghcr.io/converged-computing/metric-laghos:libfabric-gpu   | AWS | yes |[Dockerfile](docker/aws/laghos)  | Needs to be built on large machine |
| ghcr.io/converged-computing/metric-magma:libfabric        | AWS | yes |[Dockerfile](docker/aws/magma)   |  |
| ghcr.io/converged-computing/metric-minife:libfabric       | AWS | yes |[Dockerfile](docker/aws/minife)  | | 
| ghcr.io/converged-computing/metric-mixbench:libfabric     | AWS | yes |[Dockerfile](docker/aws/mixbench)| |
| ghcr.io/converged-computing/mt-gemm:libfabric             | AWS | yes |[Dockerfile](docker/aws/mt-gemm-base)| |
| ghcr.io/converged-computing/multi-gpu-models:libfabric    | AWS | yes |[Dockerfile](docker/aws/multi-gpu-models)| |
| ghcr.io/converged-computing/metric-nek5000:libfabric      | AWS | yes |[Dockerfile](docker/aws/nek5000) | |
| ghcr.io/converged-computing/metric-osu-gpu:libfabric      | AWS | yes |[Dockerfile](docker/aws/osu) | |
| ghcr.io/converged-computing/metric-quicksilver-gpu:libfabric| AWS | yes |[Dockerfile](docker/aws/quicksilver) | |
| ghcr.io/converged-computing/pytorch-resnet-experiment:libfabric-gpu | AWS   | yes |[Dockerfile](docker/aws/resnet) | |
| ghcr.io/converged-computing/metric-stream:libfabric       | AWS  | yes | [Dockerfile](docker/aws/stream) | |
| ghcr.io/converged-computing/metric-amg2023:spack-slim-cpu | Google | no |[Dockerfile](docker/google-cpu/amg2023) |  |
| ghcr.io/converged-computing/metric-lammps-cpu             | Google | no |[Dockerfile](docker/google-cpu/lammps) | |
| ghcr.io/converged-computing/metric-kripke-cpu             | Google | no |[Dockerfile](docker/google-cpu/kripke)  | |
| ghcr.io/converged-computing/metric-laghos:cpu             | Google | no |[Dockerfile](docker/google-cpu/laghos)  | |
| ghcr.io/converged-computing/metric-minife:cpu             | Google | no |[Dockerfile](docker/google-cpu/minife)  | | 
| ghcr.io/converged-computing/metric-mixbench:cpu           | Google | no |[Dockerfile](docker/google-cpu/mixbench)| |
| ghcr.io/converged-computing/metric-nek5000:cpu            | Google | no |[Dockerfile](docker/google-cpu/nek5000) | |
| ghcr.io/converged-computing/metric-osu-cpu                | Google | no |[Dockerfile](docker/google-cpu/osu) | |
| ghcr.io/converged-computing/metric-quicksilver-cpu        | Google | no |[Dockerfile](docker/google-cpu/quicksilver) | |
| ghcr.io/converged-computing/pytorch-resnet-experiment:cpu | Google | no |[Dockerfile](docker/google-cpu/resnet) | |


The AWS images are based off of the original Google cloud, but have oras and libfabric added.  The CPU variants are the same as the GPU,
with CPU stuffs removed. The exception is resnet, which uses the same pytorch base.

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
