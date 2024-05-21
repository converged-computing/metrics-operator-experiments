#!/bin/bash

appbase="/g/g92/marathe1/variorum/gpu-benchmarking/benchmarks/lgc-cap-bm/miniFE-orig/cuda/src"
nnodes=$1
ntasks=$2

inputx=620
inputy=620
inputz=620
cd ${appbase}
srun -N ${nnodes} -n ${ntasks} \
./miniFE.x nx=${inputx} ny=${inputy} nz=${inputz} \
num_devices=4 \
use_locking=1 \
elem_group_size=2 \
use_elem_mat_fields=10 \
verify_solution=0
cd -
