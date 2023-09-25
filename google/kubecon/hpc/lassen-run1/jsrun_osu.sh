#!/bin/bash
### LSF syntax
#BSUB -nnodes 128                   #number of nodes
#BSUB -W 120                    #walltime in minutes
#BSUB -G ice4hpc                   #account
#BSUB -e osu_errors.txt             #stderr
#BSUB -o osu_output.txt             #stdout
#BSUB -J kubecon_osu_128                    #name of job
#BSUB -q pbatch                   #queue to use

### Shell scripting
date; hostname
echo -n 'JobID is '; echo $LSB_JOBID
echo "Hosts: $LSB_HOSTS"
cd /g/g12/milroy1/kubecon-2023

for nnodes in {2..7}
do
    echo "Number of nodes: " $(( 2**$nnodes )) > /p/gpfs1/milroy1/kubecon/lassen_osu_$(( 2**$nnodes ))_nodes.out
    for i in {1..20}
    do
        echo "==============" >> /p/gpfs1/milroy1/kubecon/lassen_osu_$(( 2**$nnodes ))_nodes.out
        echo "Start run ${i} of 20" >> /p/gpfs1/milroy1/kubecon/lassen_osu_$(( 2**$nnodes ))_nodes.out
        #echo -e "\ntime jsrun -n $(( 2**$nnodes )) -a 1 -c 1 -r 1 -l cpu-cpu osu-micro-benchmarks-5.8/install/libexec/osu-micro-benchmarks/mpi/collective/osu_ibarrier" >> /p/gpfs1/milroy1/kubecon/lassen_osu_$(( 2**$nnodes ))_nodes.out
        #{ time -p jsrun -n $(( 2**$nnodes )) -a 1 -c 1 -r 1 -l cpu-cpu osu-micro-benchmarks-5.8/install/libexec/osu-micro-benchmarks/mpi/collective/osu_ibarrier ; } >> /p/gpfs1/milroy1/kubecon/lassen_osu_$(( 2**$nnodes ))_nodes.out 2>&1
        echo -e "\ntime jsrun -n $(( 2**$nnodes )) -a 1 -c 1 -r 1 -l cpu-cpu osu-micro-benchmarks-5.8/install/libexec/osu-micro-benchmarks/mpi/pt2pt/osu_mbw_mr" >> /p/gpfs1/milroy1/kubecon/lassen_osu_$(( 2**$nnodes ))_nodes.out
        { time -p jsrun -n $(( 2**$nnodes )) -a 1 -c 1 -r 1 -l cpu-cpu osu-micro-benchmarks-5.8/install/libexec/osu-micro-benchmarks/mpi/pt2pt/osu_mbw_mr ; } >> /p/gpfs1/milroy1/kubecon/lassen_osu_$(( 2**$nnodes ))_nodes.out 2>&1
        echo -e "\ntime jsrun -n 2 -a 1 -c 1 -r 1 -l cpu-cpu osu-micro-benchmarks-5.8/install/libexec/osu-micro-benchmarks/mpi/pt2pt/osu_latency" >> /p/gpfs1/milroy1/kubecon/lassen_osu_$(( 2**$nnodes ))_nodes.out
        { time -p jsrun -n 2 -a 1 -c 1 -r 1 -l cpu-cpu osu-micro-benchmarks-5.8/install/libexec/osu-micro-benchmarks/mpi/pt2pt/osu_latency ; } >> /p/gpfs1/milroy1/kubecon/lassen_osu_$(( 2**$nnodes ))_nodes.out 2>&1
        echo -e "\ntime jsrun -n $(( 2**$nnodes )) -a 1 -c 1 -r 1 -l cpu-cpu osu-micro-benchmarks-5.8/install/libexec/osu-micro-benchmarks/mpi/startup/osu_hello" >> /p/gpfs1/milroy1/kubecon/lassen_osu_$(( 2**$nnodes ))_nodes.out
        { time -p jsrun -n $(( 2**$nnodes )) -a 1 -c 1 -r 1 -l cpu-cpu osu-micro-benchmarks-5.8/install/libexec/osu-micro-benchmarks/mpi/startup/osu_hello ; } >> /p/gpfs1/milroy1/kubecon/lassen_osu_$(( 2**$nnodes ))_nodes.out 2>&1
        echo -e "\ntime jsrun -n $(( 2**$nnodes )) -a 1 -c 1 -r 1 -l cpu-cpu osu-micro-benchmarks-5.8/install/libexec/osu-micro-benchmarks/mpi/collective/osu_allreduce" >> /p/gpfs1/milroy1/kubecon/lassen_osu_$(( 2**$nnodes ))_nodes.out
        { time -p jsrun -n $(( 2**$nnodes )) -a 1 -c 1 -r 1 -l cpu-cpu osu-micro-benchmarks-5.8/install/libexec/osu-micro-benchmarks/mpi/collective/osu_allreduce ; } >> /p/gpfs1/milroy1/kubecon/lassen_osu_$(( 2**$nnodes ))_nodes.out 2>&1
        echo -e "End run ${i} of 20\n" >> /p/gpfs1/milroy1/kubecon/lassen_osu_$(( 2**$nnodes ))_nodes.out
    done
done

