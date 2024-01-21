# AWS Parallel Cluster

This small study aims to prototype using [AWS parallel cluster](https://docs.aws.amazon.com/parallelcluster/latest/ug/install-v3-virtual-environment.html). Note that since this requires nodejs (and I refuse to install this on my system) we will be using a Docker container. Build the container:

```bash
docker build -t cowpie .
```

Then shell in. Note that you likely want to copy over your pem keyfile (and bind the present working directory with it) to get ssh access.
 
```bash
docker run -it -v $PWD/:/tmp/data cowpie
```

`pcluster` should be on the path.

```
# which pcluster
/env/bin/pcluster
```

At this point we are following the instructions [here](https://docs.aws.amazon.com/parallelcluster/latest/ug/install-v3-configuring.html). Since we are in the container, I copied temporary credentials into it. Note that the docs/command doesn't make it clear, but running this command will _output_ this configuration file (that does not exist yet).

```bash
pcluster configure --config config-file.yaml --region us-east-1
```

After this it's interactive, and you can choose:

- a keypair (choose the one you own)
- the scheduler (slurm)
- operating system (ubuntu 22.04)
- head node instance type (I chose the tiny one for this testing)
- number of queues (1)
- name of queue (queue1)
- number of compute resources for queue (1)
- compute instance type (use tiny default)
- maximum instance count (default is 10, I did 3)
- automatic VPC creation (y)
- availability zone (default)
- both head node and compute fleet in public is OK

This should (slowly) create a configuration file?

```console
Network Configuration [Head node in a public subnet and compute fleet in a private subnet]: 2
Beginning VPC creation. Please do not leave the terminal until the creation is finalized
Creating CloudFormation stack...
Do not leave the terminal until the process has finished.
Stack Name: parallelclusternetworking-pub-20240121053431 (id: arn:aws:cloudformation:us-east-1:633731392008:stack/parallelclusternetworking-pub-20240121053431/30e40190-b81f-11ee-8b8c-0edb0fb2d51f)
Status: parallelclusternetworking-pub-20240121053431 - CREATE_COMPLETE          
The stack has been created.
Configuration file written to config-file.yaml
You can edit your configuration file or simply run 'pcluster create-cluster --cluster-configuration config-file.yaml --cluster-name cluster-name --region us-east-1' to create your cluster.
```

Note that the docs say to get exposed to EFA you just need to choose an instance type that supports it, then it should present you with the option (I did not test this) along with a placement group name. Also note that since we asked parallel cluster to create a VPC (vs. using an existing) we need to delete it ourselves later.  Here is what the resulting file looks like:

```yaml
Region: us-east-1
Image:
  Os: ubuntu2204
HeadNode:
  InstanceType: t2.micro
  Networking:
    SubnetId: subnet-0594da6fcd93e4760
  Ssh:
    KeyName: xxxxxxx
Scheduling:
  Scheduler: slurm
  SlurmQueues:
  - Name: queue1
    ComputeResources:
    - Name: t2micro
      Instances:
      - InstanceType: t2.micro
      MinCount: 0
      MaxCount: 3
    Networking:
      SubnetIds:
      - subnet-0594da6fcd93e4760
```

If we create a config we like, we won't need to run the interactive tool again. Now let's hold our breath and create it!

```bash
pcluster create-cluster --cluster-name test-cluster --cluster-configuration config-file.yaml
```

Womp womp - note for future selves. 

```
{
  "configurationValidationErrors": [
    {
      "level": "ERROR",
      "type": "KeyPairValidator",
      "message": "Ubuntu 22.04 does not support RSA keys. Please generate and use an ed25519 key"
    }
  ],
  "message": "Invalid cluster configuration."
}
```

Note that (for the meantime) I changed to an older ubuntu so it would work.

```diff
Image:
-  Os: ubuntu2204
+  Os: ubuntu2004
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
pcluster describe-cluster --cluster-name test-cluster --region us-east-1
```

This is what you see when it's done (easily 15-20 minutes)

```console
  "cloudFormationStackStatus": "CREATE_COMPLETE",
  "clusterName": "test-cluster",
  "computeFleetStatus": "RUNNING",
  "cloudformationStackArn": "arn:aws:cloudformation:us-east-1:633731392008:stack/test-cluster/3e740840-b820-11ee-a580-128f4e43a22f",
  "lastUpdatedTime": "2024-01-21T05:45:12.360Z",
  "region": "us-east-1",
  "clusterStatus": "CREATE_COMPLETE",
  "scheduler": {
    "type": "slurm"
  }
}
```

This is another way to see that:

```console
pcluster list-clusters --query 'clusters[?clusterName==`test-cluster`]' --region us-east-1
```

Now let's shell in! This is where you'll need your pem mounted in the pwd.

```console
cd /tmp/data
pcluster ssh --us-east-1 --cluster-name test-cluster -i ./path-to.pem
```

This cluster has the same issue as on Google Cloud but slightly worse - we can't even ask for 1 node because it's not provisioned yet. I waited a while and:

```
$ sinfo
PARTITION AVAIL  TIMELIMIT  NODES  STATE NODELIST
queue1*      up   infinite      3  idle# queue1-dy-t2micro-[1-3]
```

That's weird - srun doesn't work. Let's try a sleep batch script instead.

```
#!/bin/bash
sleep 30
echo "Hello World from $(hostname)"
```

That seemed to work. I'm not sure why srun did not.

```bash
$ sbatch ./sleep.sh 
Submitted batch job 5
ubuntu@ip-10-0-6-100:~$ squeue
             JOBID PARTITION     NAME     USER ST       TIME  NODES NODELIST(REASON)
                 5    queue1 sleep.sh   ubuntu CF       0:02      1 queue1-dy-t2micro-1
```

When you are done, exit and delete the cluster.

```bash
pcluster delete-cluster --region us-east-1 --cluster-name test-cluster
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


## Thinking Big Picture

The tool has a fairly specific [set of instructions](https://docs.aws.amazon.com/parallelcluster/latest/ug/building-custom-ami-v3.html) for building a custom AMI, and it does this by starting with our AMI as a base. At face value, I don't see that this will easily map into a common VM that we could share between clouds, but I do think we could do our best to make them comparable. For example, pcluster is going to likely have EFA, and that's not needed on Google Cloud. pcluster is built from a chef [cookbook](https://github.com/aws/aws-parallelcluster-cookbook/tree/develop/cookbooks/aws-parallelcluster-slurm) that The Google Cloud images likely are starting with their HPC optimized images, and that's not a thing on AWS. We can talk further about a strategy. My suggestion:

- decide on the core of what we want for a VM
- we can likely choose an AMI and then [port it over to Google Cloud](https://cloud.google.com/compute/docs/import/import-aws-image) for use with our base image there. Likely that can be built with most of the bare metal stuff we need.
- But the details of slurm and what we install on top of it matter! So we can write down what we can customize for each (and the defaults) and sanity check they are comparable. We can tweak what is needed.
- Then decide if this approach is sound, and think of other ideas if not.
