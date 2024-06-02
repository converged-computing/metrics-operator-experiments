# "Bare Metal" on AWS

This could either be parallel cluster or a terraform deployment. Since I don't want to re-learn slurm, I'm going to use [a terraform setup](https://github.com/converged-computing/flux-aws) first.

## Experiment

### 1. Setup

From [this directory](https://github.com/converged-computing/flux-aws/tree/main/tf/hpc6a) edit the configuration for your VM base, key, and size that you want. Then type `make` to validate and bring up the setup.
Get the topology:

```bash
aws ec2 describe-instance-topology --region us-east-2 --filters Name=instance-type,Values=hpc6a.48xlarge > topology-2.json
aws ec2 describe-instances --filters "Name=instance-type,Values=hpc6a.48xlarge" --region us-east-1 > instances-2.json
```

You'll then need to get the first listed instance in the GUI (that should be the lead broker, since the same ABC listing is used to populate broker.toml, and the first in the list is index 0 / lead) and shell in. Something like:

```bash
$ ssh -i ~/.ssh/mykey.pem -o IdentitiesOnly=yes ubuntu@ec2-xx-xxx-xxx-xx.us-east-2.compute.amazonaws.com
```

Sanity check efa is there.

```
# fi_info  | less
provider: efa
    fabric: efa
    domain: rdmap0s31-rdm
    version: 121.0
    type: FI_EP_RDM
    protocol: FI_PROTO_EFA
provider: efa
    fabric: efa
    domain: rdmap0s31-dgrm
    version: 121.0
    type: FI_EP_DGRAM
    protocol: FI_PROTO_EFA
```

Let's cleanup the singularity install.

```bash
rm -rf singularity-ce-4.1.3
rm singularity-c2*.tar.gz
```

### 2. Applications

Let's do it! We will pull each application to all nodes, and then run a test.
Note that if we use this approach, we can pre-pull all images and save that time.

#### AMG2023

Create the minicluster and shell in.

```bash
time flux exec -r all singularity pull docker://ghcr.io/converged-computing/metric-amg2023:spack-slim-cpu
```

Pull time: 1 minute 20 seconds.
Since this container requires sourcing spack, we need to write a bash script to run on the host.

```bash
#!/bin/bash
# run-amg.sh
. /etc/profile.d/z10_spack_environment.sh
amg -P 12 8 4 -n 64 64 128
```
And then copy the script and run.

```bash
flux archive create --name amg -C /home/ubuntu run-amg.sh
flux exec -x 0 flux archive extract --name amg -C /home/ubuntu
flux start mpirun -n 12 singularity exec metric-amg2023_spack-slim-cpu.sif /bin/bash ./run-amg.sh
time flux run -N 2 -n 192 singularity exec metric-amg2023_spack-slim-cpu.sif /bin/bash ./run-amg.sh
```

I couldn't get this working with flux, so I tried mpirun alone:

```
mpirun --hostfile ./hostlist.txt -N 2 -n 192 singularity exec metric-amg2023_spack-slim-cpu.sif /bin/bash ./run-amg.sh
```
That didn't work either - I suspect the spack environment / bash script is adding issue. Needs more thinking - maybe requiring bindings to the host (ew).


#### Kripke

```bash
# 1 minute and change (forgot to write down, maybe 1m50 seconds)?
time flux exec -r all singularity pull docker://ghcr.io/converged-computing/metric-kripke-cpu:libfabric

# works!
# 2m 49 seconds
time flux run -N 2 -n 192 -o cpu-affinity=per-task singularity exec metric-kripke-cpu_libfabric.sif kripke --layout GDZ --dset 8 --zones 96,96,96 --gset 16 --groups 64 --niter 10 --legendre 9 --quad 8 --procs 4,6,8
```

#### Linpack

```bash
# 1 minute 17 seconds
time flux exec -r all singularity pull docker://ghcr.io/converged-computing/metric-linpack-cpu:libfabric

# 6.879 seconds for: /opt/hpl/hpl-2.3/testing/ptest
time flux run -N 2 -n 192 -o cpu-affinity=per-task singularity exec --pwd /opt/hpl/hpl-2.3/testing/ptest/ metric-linpack-cpu_libfabric.sif xhpl
```

#### Laghos

```bash
# 1 minute 4 seconds
time flux exec -r all singularity pull docker://ghcr.io/converged-computing/metric-laghos:libfabric-cpu

# 8.97 seconds
time flux run -N 2 -n 192 -o cpu-affinity=per-task singularity exec --pwd /opt/laghos metric-laghos_libfabric-cpu.sif /opt/laghos/laghos -p 1 -m ./data/cube01_hex.mesh -rs 2 -tf 0.6 -pa -cfl 0.08 --max-steps 20
```

#### LAMMPS

```bash
# 1 minute 17 seconds
time flux exec -r all singularity pull docker://ghcr.io/converged-computing/metric-lammps-cpu

# Wrong permissions on scripts, oups
mkdir -p lammps
singularity exec metric-lammps-cpu_latest.sif cp -R /code ./lammps
sudo chown -R ubuntu ./lammps
flux exec -r all -x 0 mkdir -p /home/ubuntu/lammps/code
flux archive create --name lammps -C /home/ubuntu/lammps code
flux exec -x 0 flux archive extract --name lammps -C /home/ubuntu/lammps

# 26.19 seconds
time flux run -N 2 -n 192 -o cpu-affinity=per-task singularity exec --pwd /home/ubuntu/lammps/code metric-lammps-cpu_latest.sif lmp -in in.snap.test -var snapdir 2J8_W.SNAP -v x 228 -v y 228 -v z 228 -var nsteps 20000
```

#### MiniFE

```bash
# 59.29 seconds
time flux exec -r all singularity pull docker://ghcr.io/converged-computing/metric-minife:libfabric-cpu

# 57 seconds
time flux run -N 2 -n 192 -o cpu-affinity=per-task singularity exec metric-minife_libfabric-cpu.sif miniFE.x nx=620 ny=620 nz=620 num_devices=4 use_locking=1 elem_group_size=2 use_elem_mat_fields=10 verify_solution=0
```

#### Mixbench

```bash
# 59.67 seconds
time flux exec -r all singularity pull docker://ghcr.io/converged-computing/metric-mixbench:libfabric-cpu

# 38.23 seconds
time flux run -N 2 -n 192 -o cpu-affinity=per-task singularity exec metric-mixbench_libfabric-cpu.sif mixbench-cpu
```

Again, this seems like it's for one node only, and needs a wrapper.

#### Mt Gem

```bash
1 minute 8 seconds
time flux exec -r all singularity pull docker://ghcr.io/converged-computing/mt-gemm:libfabric-cpu

# 6.9 seconds
time flux run -N 2 -n 192 -o cpu-affinity=per-task singularity exec mt-gemm_libfabric-cpu.sif /opt/dense_linear_algebra/gemm/mpi/build/1_dense_gemm_mpi
```

#### Nek5000

```bash
# 1 minute 17 seconds
time flux exec -r all singularity pull docker://ghcr.io/converged-computing/metric-nek5000:libfabric-cpu

# Try writing data to local filesystem, sharing with workers
mkdir -p nekrs
singularity exec metric-nek5000_libfabric-cpu.sif cp -R /opt/nekrs/examples/turbPipe ./nekrs
flux exec -r all -x 0 mkdir -p /home/ubuntu/nekrs
flux archive create --name nekrs -C /home/ubuntu nekrs
flux exec -x 0 flux archive extract --name nekrs -C /home/ubuntu

# This is going to fail...
time flux run -N 2 -n 192 -o cpu-affinity=per-task singularity exec --pwd /home/ubuntu/nekrs metric-nek5000_libfabric-cpu.sif nekrs --setup turbPipe.par

# But then we can copy the cache over
flux archive create --name nekrs-cache -C /home/ubuntu/nekrs .cache
flux exec -x 0 flux archive extract --name nekrs-cache -C /home/ubuntu/nekrs

# Now run again (it will fail again) we now need the udf part
time flux run -N 2 -n 192 -o cpu-affinity=per-task singularity exec --pwd /home/ubuntu/nekrs metric-nek5000_libfabric-cpu.sif nekrs --setup turbPipe.par

flux archive remove --name nekrs-cache
flux archive create --name nekrs-cache -C /home/ubuntu/nekrs .cache
flux exec -x 0 flux archive extract --overwrite --name nekrs-cache -C /home/ubuntu/nekrs

# This one will (finally) work.
time flux run -N 2 -n 192 -o cpu-affinity=per-task singularity exec --pwd /home/ubuntu/nekrs metric-nek5000_libfabric-cpu.sif nekrs --setup turbPipe.par
```

This hangs at a checkpoint so I'm not sure it will actually run. I waited 15+ minutes and no progress and killed it.

#### OSU

```bash
# 1 minute 12 seconds
time flux exec -r all singularity pull docker://ghcr.io/converged-computing/metric-osu-cpu:libfabric

# 2.88 seconds
time flux run -N 2 -n 2 -o cpu-affinity=per-task singularity exec metric-osu-cpu_libfabric.sif /opt/osu-benchmark/build.openmpi/mpi/pt2pt/osu_bw

# 9.925 seconds
time flux run -N 2 -n 2 -o cpu-affinity=per-task singularity exec metric-osu-cpu_libfabric.sif /opt/osu-benchmark/build.openmpi/mpi/pt2pt/osu_latency

# 2.88 seconds
time flux run -N 2 -n 192 -o cpu-affinity=per-task singularity exec metric-osu-cpu_libfabric.sif /opt/osu-benchmark/build.openmpi/mpi/collective/osu_allreduce
```

#### Quicksilver

```bash
# 1 minute 12 seconds
time flux exec -r all singularity pull docker://ghcr.io/converged-computing/metric-quicksilver-cpu:libfabric

# Akin to others, this just hangs.
time flux run -N 2 -n 192 -o cpu-affinity=per-task singularity exec metric-quicksilver-cpu_libfabric.sif qs --inputFile /opt/quicksilver/Examples/CORAL2_Benchmark/Problem1/Coral2_P1.inp

# If I reduce n, it runs!
# 4m 53 seconds
time flux run -N 2 -n 8 -o cpu-affinity=per-task singularity exec metric-stream-cpu_libfabric.sif stream_c.exe 
```

#### Stream

```bash
# 59.99 seconds!
time flux exec -r all singularity pull docker://ghcr.io/converged-computing/metric-stream:libfabric-cpu

# 5.72 seconds
time flux run -N 2 -n 192 -o cpu-affinity=per-task singularity exec metric-stream_libfabric-cpu.sif  stream_c.exe
```

Note this warning:

```
Solution Validates: avg error less than 1.000000e-13 on all three arrays
```

### Clean Up

When you are done, `make destroy` will destroy the cluster.
