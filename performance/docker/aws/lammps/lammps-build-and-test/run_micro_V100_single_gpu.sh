#!/bin/bash -l

LSF_JOB_ID=9999
SLURM_NTASKS=1
gpus_per_node=1
# spec.txt provides the input specification
# by defining the variables spec and BENCH_SPEC
source micro_spec.txt

mkdir lammps_$spec.$SLURM_JOB_ID
cd    lammps_$spec.$SLURM_JOB_ID
ln -s ../../common .
cp ../micro_spec.txt .

# This is needed if LAMMPS is built using cmake.
install_dir=/g/g92/marathe1/variorum/gpu-benchmarking/benchmarks/lgc-cap-bm/lammps_base/install_V100
export LD_LIBRARY_PATH=${install_dir}/lib64:$LD_LIBRARY_PATH
EXE=${install_dir}/bin/lmp

input="-k on g $gpus_per_node -sf kk -pk kokkos newton on neigh half ${BENCH_SPEC} "

command="srun -n $SLURM_NTASKS $EXE $input"

echo $command

$command
