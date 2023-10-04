#!/bin/bash

#SBATCH -N 128
#SBATCH -J lammps
#SBATCH -t 02:00:00
#SBATCH -p pbatch
#SBATCH --mail-type=ALL
#SBATCH -A cnvgdcmp

cd /g/g12/milroy1/kubecon-2023/lammps_ruby/lammps/examples/reaxff/HNS/

lammps=/g/g12/milroy1/kubecon-2023/lammps_ruby/lammps/bin/bin/lmp
problem="-v x 64 -v y 16 -v z 16 -in in.reaxc.hns -nocite"

output=/p/lustre1/milroy1/kubecon-2023/lammps_ruby

for ranks in 400 800 1600 3200 6400
do
    for i in {1..5}
    do
        outfile=${output}/ruby_lammps_${ranks}_${i}_ranks.out
        echo -e "\nsrun -N $(( $ranks/50 )) -n $ranks --cpus-per-task=1 --ntasks-per-node=50 ${lammps} ${problem}" >> ${outfile}
        srun -N $(( $ranks/50 )) -n $ranks --cpus-per-task=1 --ntasks-per-node=50 ${lammps} ${problem} 2>&1 >> ${outfile}
    done
done

