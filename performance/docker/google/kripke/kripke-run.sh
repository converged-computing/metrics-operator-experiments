#!/bin/bash

# Kripke run script: Assumes 2 nodes with 4 V100 GPUs each
# Also assumes that Kripke is built with MPI and CUDA enabled

nnodes=2
ntasks=8
kripke_bin=/g/g92/marathe1/variorum/gpu-benchmarking/benchmarks/lgc-cap-bm/Kripke-new-orig/Kripke-new/build-mpi-gpu/kripke.exe

CUDA_VISIBLE_DEVICES=0,1,2,3 \
    srun -N $nnodes -n $ntasks \
    ./${kripke_bin} \
    --arch CUDA \
    --layout GDZ \
    --dset 8 \
    --zones 128,72,128 \ #largest that can fit on a Lassen node (15.5GB GPU mem)
    --gset 16 \
    --groups 64 \
    --niter 50 \  # Can increase this to increase total runtime
    --legendre 8 \
    --quad 8 \
    --procs 2,2,2 # <x,y,z> where ntasks == x*y*z, can be asymmetric
