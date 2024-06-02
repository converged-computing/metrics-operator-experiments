# AWS Parallel Cluster

This setup study aims to prototype using [AWS parallel cluster](https://docs.aws.amazon.com/parallelcluster/latest/ug/install-v3-virtual-environment.html). Note that since this requires nodejs (and I refuse to install this on my system) we will be using a Docker container. It is extended from [our original test](https://github.com/converged-computing/metrics-operator-experiments/tree/main/performance/testing/slurm/aws-0). Build the container:

```bash
docker build -t cowpie .
```

💩️

## Usage

### 1. Prepare Install Script

We need to install Singularity on all the nodes, so upload that script to a bucket:

```bash
aws s3 cp --acl public-read parallel-cluster-performance-study-install.sh s3://<bucket-name>/parallel-cluster-performance-study-install.sh

# E.g.,
aws s3 cp --acl public-read parallel-cluster-performance-study-install.sh s3://performance-study-ldrd/parallel-cluster-performance-study-install.sh
```

Note that I did this in the interface and made it public because I don't have patience for AWS json permissions policy files! Make sure you edit [config-file.yaml](config-file.yaml) to reflect this path. Note that for this first round I'm going to try running this install as a job - I was trying to minimize the moving pieces.

### 2. Shell into container

Then shell in. Note that you likely want to copy over your pem keyfile (and bind the present working directory with it) to get ssh access.
 
```bash
# For this you will need to export AWS credentials
docker run --workdir /tmp/data -it -v $PWD/:/tmp/data cowpie

# This uses default credentials
docker run --workdir /tmp/data -it -v $PWD/:/tmp/data -v /home/vanessa/.aws:/root/.aws  cowpie
```

`pcluster` should be on the path.

```
# which pcluster
/env/bin/pcluster
```

### 3. Automate subnet

I had trouble creating the subnet, so I used `pcluster configure` first to make it for me (and in the right zone, etc).

```bash
cd /tmp
pcluster configure --config make-subnet.yaml --region us-east-2
```
Here were my choices:

```console
INFO: Configuration file make-subnet.yaml will be written.
Press CTRL-C to interrupt the procedure.


Allowed values for EC2 Key Pair Name:
1. ...
Allowed values for Scheduler:
1. slurm
2. awsbatch
Scheduler [slurm]: 1
Allowed values for Operating System:
1. alinux2
2. centos7
3. ubuntu2004
4. ubuntu2204
5. rhel8
6. rocky8
7. rhel9
8. rocky9
Operating System [alinux2]: 3
Head node instance type [t2.micro]: hpc6a.48xlarge
Number of queues [1]: 1
Name of queue 1 [queue1]: 
Number of compute resources for queue1 [1]: 
Compute instance type for compute resource 1 in queue1 [t2.micro]: hpc6a.48xlarge
The EC2 instance selected supports enhanced networking capabilities using Elastic Fabric Adapter (EFA). EFA enables you to run applications requiring high levels of inter-node communications at scale on AWS at no additional charge (https://docs.aws.amazon.com/parallelcluster/latest/ug/efa-v3.html).
Enable EFA on hpc6a.48xlarge (y/n) [y]: y
Maximum instance count [10]: 3
Enabling EFA requires compute instances to be placed within a Placement Group. Please specify an existing Placement Group name or leave it blank for ParallelCluster to create one.
Placement Group name []: performance-study
Automate VPC creation? (y/n) [n]: y
Allowed values for Availability Zone:
1. us-east-2b
Availability Zone [us-east-2b]: 1
Allowed values for Network Configuration:
1. Head node in a public subnet and compute fleet in a private subnet
2. Head node and compute fleet in the same public subnet
Network Configuration [Head node in a public subnet and compute fleet in a private subnet]: 2
Beginning VPC creation. Please do not leave the terminal until the creation is finalized
Creating CloudFormation stack...
Do not leave the terminal until the process has finished.
Stack Name: parallelclusternetworking-pub-20240601045123 (id: arn:aws:cloudformation:us-east-2:633731392008:stack/parallelclusternetworking-pub-20240601045123/bffa7470-1fd2-11ef-bf57-06b62ba9e52d)
Status: parallelclusternetworking-pub-20240601045123 - CREATE_COMPLETE          
The stack has been created.
Configuration file written to make-subnet.yaml
You can edit your configuration file or simply run 'pcluster create-cluster --cluster-configuration make-subnet.yaml --cluster-name cluster-name --region us-east-2' to create your cluster.
```

The main thing that matters is the VPC/subnet I think. Then copy over those parts of the conig file.


### 4. Create the pcluster!

We already have our [config-file.yaml](config-file.yaml)

```bash
pcluster create-cluster --cluster-name test-cluster --cluster-configuration config-file.yaml
```

That seemed to work! Of course we aren't actively monitoring the creation status.

```console
{
  "cluster": {
    "clusterName": "test-cluster",
    "cloudformationStackStatus": "CREATE_IN_PROGRESS",
    "cloudformationStackArn": "arn:aws:cloudformation:us-east-1:633731392008:stack/test-cluster/xxxxxxxxxxxxx,
    "region": "us-east-1",
    "version": "3.8.0",
    "clusterStatus": "CREATE_IN_PROGRESS",
    "scheduler": {
      "type": "slurm"
    }
  }
}
```

We can do that as follows:

```bash
pcluster describe-cluster --cluster-name test-cluster --region us-east-2
```

This is what you see when it's done (easily 15-20 minutes)

```console
[
  {
    "clusterName": "test-cluster",
    "cloudformationStackStatus": "CREATE_COMPLETE",
    "cloudformationStackArn": "arn:aws:cloudformation:us-east-2:633731392008:stack/test-cluster/7dd6bbc0-1fd3-11ef-a35d-0ab4855fa11f",
    "region": "us-east-2",
    "version": "3.9.2",
    "clusterStatus": "CREATE_COMPLETE",
    "scheduler": {
      "type": "slurm"
    }
  }
]

```

You can also watch cloud formation in the AWS console. This is another way to see that:

```console
pcluster list-clusters --query 'clusters[?clusterName==`test-cluster`]' --region us-east-2
```

Now let's shell in! This is where you'll need your pem mounted in the pwd.

```console
pcluster ssh --region us-east-2 --cluster-name test-cluster -i ./path-to.pem
```

**IMPORTANT** I spent two days trying to debug why my pem key didn't work, and one that had worked before, and (for some reason) it was just old, because I created a new one and it worked. If you get permission denied try making a new one. 🙃️

Note that since we asked for our nodes (minimum) to be created off the bat, we shouldn't have to wait. If you did a minimum value of 1, you would need to wait, which isn't ideal. This should be available immediately:

```bash
$ sinfo
PARTITION AVAIL  TIMELIMIT  NODES  STATE NODELIST
queue1*      up   infinite      3   idle queue1-st-hpc6a48xlarge-[1-3]
```

Let's try creating a job to install singularity, the script [install-job.sh](install-job.sh).

That seemed to work. I'm not sure why srun did not.

```bash
$ sbatch -N 2 ./install-job.sh
Submitted batch job 1
ubuntu@ip-10-0-0-109:~$ squeue
             JOBID PARTITION     NAME     USER ST       TIME  NODES NODELIST(REASON)
                 1    queue1 install-   ubuntu  R       0:17      3 queue1-st-hpc6a48xlarge-[1-3]
```

I also ran the script locally to install on the head node. This makes me realize we probably want a shared directory to pull / use containers from.

```bash
/bin/bash ./install-job.sh
```

At this point you can run experiments! I'm going to prototype with flux with VMs since we are intending to run there - I don't want to learn slurm again.
When you are done, exit and delete the cluster.

```bash
pcluster delete-cluster --region us-east-2 --cluster-name test-cluster
```

Delete the parallel cluster stack:

```bash
aws --region us-east-1 cloudformation list-stacks \
   --stack-status-filter "CREATE_COMPLETE" \
   --query "StackSummaries[].StackName" | \
   grep -e "parallelclusternetworking-" 
```

And then find the parallel cluster one and delete it.

```bash
aws --region us-east-1 cloudformation delete-stack \
   --stack-name parallelclusternetworking-pub-20240121053431
```

And don't forget to delete the VPC manually in the interface!
