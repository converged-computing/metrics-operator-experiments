#!/bin/bash
### LSF syntax
#BSUB -nnodes 160                 #number of nodes
#BSUB -W 240                      #walltime in minutes
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
cd /g/g0/sochat1/kubecon-2023/lammps/examples/reaxff/HNS/
mkdir -p /p/gpfs1/sochat1/kubecon/

# What I tried on an allocation of 2 nodes
# jsrun lmp -v x 2 -v y 2 -v z 2 -in in.reaxc.hns -nocite
lmp=/g/g0/sochat1/kubecon-2023/lammps/bin/bin/lmp
problem="-v x 64 -v y 16 -v z 16 -in in.reaxc.hns -nocite"

# Command from milroy
# jsrun -p 40 --rs_per_socket=1 -c 20 -r 2 -l cpu-cpu /g/g0/sochat1/kubecon-2023/lammps/bin/bin/lmp -v x 2 -v y 2 -v z 2 -in in.reaxc.hns -nocite
# time -p jsrun -p $ranks --rs_per_socket=1 -c 20 -r 2 -l cpu-cpu ${lmp} ${problem} >> ${outfile} &

# To submit
# bsub < jsrun_lammps.sh
output=/p/gpfs1/sochat1/kubecon

# We need to make sure we only use this number of ranks
# On cloud, this was 8, 16, 32, 64, 128 nodes
for ranks in 400 800 1600 3200 6400
do
    for i in {1..5}
    do
        outfile=${output}/lassen_lammps_${ranks}_${i}_ranks.out
        echo -e "\njsrun -p $ranks --rs_per_socket=1 -c 20 -r 2 --stdio_stderr=${outfile} --stdio_stdout=${outfile} ${lmp} ${problem}" >> ${outfile}
        jsrun -p $ranks --rs_per_socket=1 -c 20 -r 2 --stdio_stderr=${outfile} --stdio_stdout=${outfile} ${lmp} ${problem}
    done
done
