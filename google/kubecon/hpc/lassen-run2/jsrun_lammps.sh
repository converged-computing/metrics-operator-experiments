#!/bin/bash
### LSF syntax
#BSUB -nnodes 160                 #number of nodes
#BSUB -W 120                      #walltime in minutes
#BSUB -G cnvgdcmp                 #account
#BSUB -e lammps_errors.txt        #stderr
#BSUB -o lammps_output.txt        #stdout
#BSUB -J kubecon_lammps_128       #name of job
#BSUB -q pbatch                   #queue to use

### Shell scripting
date; hostname
echo -n 'JobID is '; echo $LSB_JOBID
echo "Hosts: $LSB_HOSTS"
export PATH=$PATH:/g/g0/sochat1/kubecon-2023/lammps/bin/bin
cd /g/g0/sochat1/kubecon-2023/lammpps/examples/reaxff/HNS/
mkdir -p /p/gpfs1/sochat1/kubecon/

# What I tried on an allocation of 2 nodes
# jsrun lmp -v x 2 -v y 2 -v z 2 -in in.reaxc.hns -nocite
lmp=/g/g0/sochat1/kubecon-2023/lammps/bin/bin/lmp

# TODO I didn't change jsrun arguments because I don't have a clue
# We need to make sure we only use this number of ranks
# On cloud, this was 4, 8, 16, 32, 64, 128 nodes
for ranks in 200 400 800 1600 3200 6400
do
    outfile=/p/gpfs1/sochat1/kubecon/lassen_lammps_${ranks}_ranks.out
    echo "Number of ranks: ${ranks}" > $outfile
    for i in {1..20}
    do
        echo "==============" >> $outfile
        echo "Start run ${i} of 20" >> $outfile
        echo -e "\ntime jsrun -n $ranks -a 1 -c 1 -r 1 -l cpu-cpu ${lmp}" >> ${output}
        { time -p jsrun -n $ranks -a 1 -c 1 -r 1 -l cpu-cpu ${lmp}; } >> ${output} 2>&1
        echo -e "\ntime jsrun -n 2 -a 1 -c 1 -r 1 -l cpu-cpu ${lmp}" >> ${output}
        { time -p jsrun -n 2 -a 1 -c 1 -r 1 -l cpu-cpu ${lmp} ; } >> ${output} 2>&1
        echo -e "\ntime jsrun -n $ranks -a 1 -c 1 -r 1 -l cpu-cpu ${lmp}" >> $output
        { time -p jsrun -n $ranks -a 1 -c 1 -r 1 -l cpu-cpu ${lmp} ; } >> $output 2>&1
        echo -e "\ntime jsrun -n $ranks -a 1 -c 1 -r 1 -l cpu-cpu ${lmp}" >> $output
        { time -p jsrun -n $ranks -a 1 -c 1 -r 1 -l cpu-cpu ${lmp} ; } >> $output 2>&1
        echo -e "End run ${i} of 20\n" >> $output
    done
done

