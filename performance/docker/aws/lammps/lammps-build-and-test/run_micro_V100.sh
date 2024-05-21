#!/bin/bash -l

# LAMMPS run script for relatively small input on V100.
# You'll need to modify the following variables to run LAMMPS on your system:
# - $NNODES: number of nodes/instances to run on
# - $NTASKS: total number of tasks in the run
# - $gpus_per_node: #GPUs per node. 4 on Lassen.
# - $install_dir: Path for LAMMPS install
## NOTE: 'srun' may not be present on all test systems, so there needs to be a 
#        way to populate the hostfile that we can then pass to `mpirun'.

install_dir=/g/g92/marathe1/variorum/gpu-benchmarking/benchmarks/lgc-cap-bm/lammps_base/install_V100
LSF_JOB_ID=9999
NNODES=2
NTASKS=8
gpus_per_node=4
TASKS_PER_NODE=`echo $NTASKS/$NNODES | bc`

# spec.txt provides the input specification
# by defining the variables spec and BENCH_SPEC
source micro_spec.txt

mkdir lammps_$spec.$SLURM_JOB_ID
cd    lammps_$spec.$SLURM_JOB_ID
ln -s ../../common .
cp ../micro_spec.txt .

# Required step: generate a hostfile for mpirun. On Lassen, that can be done with srun
srun -N $NNODES -n $NNODES hostname > hostfile

# This is needed if LAMMPS is built using cmake.
export LD_LIBRARY_PATH=${install_dir}/lib64:$LD_LIBRARY_PATH
EXE=${install_dir}/bin/lmp

input="-k on g $gpus_per_node -sf kk -pk kokkos newton on neigh half ${BENCH_SPEC} "

command="mpirun -np $NTASKS --hostfile hostfile -N $TASKS_PER_NODE $EXE $input"

echo $command

$command
