#!/bin/bash
/opt/intel/mpi/2021.8.0/bin/mpirun --hostfile ./hostlist.txt -np 4 --map-by socket lmp -v x 2 -v y 2 -v z 2 -in in.reaxc.hns -nocite  2>&1 | tee -a lammps.out
