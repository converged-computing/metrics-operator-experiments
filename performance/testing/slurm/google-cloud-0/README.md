# Google Cloud Prototype

We are going to naively follow the instructions [here](https://cloud.google.com/hpc-toolkit/docs/quickstarts/slurm-cluster) to
test deploying a small SLURM cluster to Google Cloud.

1. Note that I had most APIs enabled, but needed to enable the last one (secrets API)
2. They make you estimate your own costs.
  - I estimated ~$30 for compute / month, and Filestore would be $188/ month. TLDR this will be trivial for a quick up and down test!
3. I already had the default service account enabled for compute engine.

## Tutorial

Clone the hpc-toolkit and build it. You need to have Go installed.

```bash
git clone https://github.com/GoogleCloudPlatform/hpc-toolkit.git
cd hpc-toolkit/
make
```
```console
./ghpc --version
ghpc version v1.27.0
Built from 'main' branch.
Commit info: v1.27.0-0-gfcdc5e5e
```

I think this might throw up on you if you don't have [packer](https://developer.hashicorp.com/packer/tutorials/docker-get-started/get-started-install-cli) installed (I already had it so I can't verify that). 
But that answers our first question - we have a VM base here that we are building!  This is really cool - the tool uses a yaml configuration file to create a deployment directory. E.g.,:

> An HPC blueprint is a YAML file that defines the HPC environment. The ghpc command, that is built in previous step, uses the HPC blueprint to create a deployment folder. The deployment folder can then be used to deploy the environment.

I took a look at the [hpc-slurm.yaml](https://github.com/GoogleCloudPlatform/hpc-toolkit/blob/main/examples/hpc-slurm.yaml) and what I see:

 - references to community [modules](https://github.com/GoogleCloudPlatform/hpc-toolkit/tree/main/modules) that are served alongside the repository
 - these are just Terraform modules! Now I see why Ward was developing the scientific computing examples with Terraform (they could end up here)

So high level - hpc-toolkit is a wrapper for deploying terraform modules! The yaml we are using to make a deployment folder is just providing a simpler way to define variables for that. I actually really like that, because (if you are able to make a reliable, hardened terraform module) this exposes it in a really simple, intuitive way.

So we can do:

```bash
GOOGLE_PROJECT=myproject
./ghpc create examples/hpc-slurm.yaml -l ERROR --vars project_id=$GOOGLE_PROJECT
```
```console
To deploy your infrastructure please run:

./ghpc deploy hpc-small

Find instructions for cleanly destroying infrastructure and advanced manual
deployment instructions at:

hpc-small/instructions.txt
```

And then this command is just running the terraform apply! Note that you need terraform installed. I had opentofu. I tried to be deviant and try this:

```bash
sudo ln -s /usr/bin/tofu /usr/bin/terraform
```

Muahahah! But it didn't work. So I installed terraform. 

```bash
sudo rm /usr/bin/terraform
wget https://releases.hashicorp.com/terraform/1.7.0/terraform_1.7.0_linux_amd64.zip
unzip terraform_1.7.0_linux_amd64.zip 
sudo mv terraform /usr/local/bin/
rm terraform_1.7.0_linux_amd64.zip 
```

Now try this.

```bash
./ghpc deploy hpc-small
```
```console
Initializing deployment group hpc-small/primary
Testing if deployment group hpc-small/primary requires adding or changing cloud infrastructure
Deployment group hpc-small/primary requires adding or changing cloud infrastructure
Summary of proposed changes: Plan: 33 to add, 0 to change, 0 to destroy.
(D)isplay full proposed changes,
(A)pply proposed changes,
(S)top and exit,
(C)ontinue without applying
Please select an option [d,a,s,c]: A
```

And then wait a bit...

```console
[0]: Creation complete after 13s [id=projects/llnl-flux/zones/us-central1-a/instances/hpcsmall-login-xzdhv8ku-001]

Apply complete! Resources: 33 added, 0 changed, 0 destroyed.
Collecting terraform outputs from hpc-small/primary
Deployment group primary contains no artifacts to export

###############################
Find instructions for cleanly destroying infrastructure and advanced manual
deployment instructions at:

hpc-small/instructions.txt
```

Then login to the console and see your cluster! It has a nice slurm logo entry :)
Note the tutorial says there are 3 nodes but I just had 1 for debug. I suspect I only saw 1
because autoscaling is going to drive the needs of the cluster, e.g.,:

```yaml
  - id: debug_node_group
    source: community/modules/compute/schedmd-slurm-gcp-v5-node-group
    settings:
      node_count_dynamic_max: 4
      machine_type: n2-standard-2
```

And I didn't feel like waiting. I suspect if/when we set this up we will want to disable autoscaling and ask for an explicit
number of set nodes. When you are done you can clean up.

```bash
terraform -chdir=hpc-small/primary destroy -auto-approve
```

Note that I unfortunately got a few errors cleaning up, and had to manually delete resources and run again (subnetworks being used by instances that were created after I think).
And double check all the console interfaces (VMs, filestore) to make sure this is truly the case.

## Thinking Big Picture

The pros of using this for Google Cloud is that they have put thought into getting the best setup for filesystem, etc.
We also have pretty good power to customize the [image](https://github.com/GoogleCloudPlatform/hpc-toolkit/tree/main/modules/packer/custom-image),
which largely is going to come down to us making a custom image build, if needed. The biggest challenge here will be making something
that we can match to parallel cluster. If the common unit is using packer, I am hopeful this won't be too hard, although I haven't
tried Parallel cluster and don't know how that can accept a custom VM. But it seems we have good flexibility here.

An alternative is [magic castle](https://github.com/ComputeCanada/magic_castle) for which they already have thought about common setups across clouds. The issue here would
be the same that we need to figure out how to customize for (likely) our common image, so I don't know if we get any additional benefit there.
