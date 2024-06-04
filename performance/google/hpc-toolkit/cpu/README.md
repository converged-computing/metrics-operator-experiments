# Google Cloud Prototype

This will deploy a small SLURM cluster to Google Cloud. See the notes at the top of [hpc-slurm.yaml](hpc-slurm.yaml) for changes you might want to make.

1. Note that I had most APIs enabled, but needed to enable the last one (secrets API)
2. They make you estimate your own costs. 
3. I already had the default service account enabled for compute engine.

## Tutorial

Clone the hpc-toolkit and build it. You need to have Go installed and [packer too](https://developer.hashicorp.com/packer/tutorials/docker-get-started/get-started-install-cli)

```bash
git clone https://github.com/GoogleCloudPlatform/hpc-toolkit.git
cd hpc-toolkit/
make
```
```console
./ghpc --version
ghpc version v1.34.2
Built from 'main' branch.
Commit info: v1.34.2-0-g2af3c420

# Note this is the verison when we initially tested months ago
Commit info: v1.27.0-0-gfcdc5e5e
```

Go up one directory to our cluster config:

```bash
cd ../
```

Note that the Google Project is in the config. So we can do:

```bash
./hpc-toolkit/ghpc create ./hpc-slurm.yaml -l ERROR
```

That creates a new directory. Then follow the instructions:

```bash
./hpc-toolkit/ghpc deploy performance-study
```

To bring it down:

```bash
./hpc-toolkit/ghpc destroy performance-study --auto-approve
```

Damn that was so much easier than the other clouds, sorry have to say it!
Note that there was some small issues with cleanup for me - the cluster seemed to add nodes and then I wasn't able to delete the network. I manually deleted the VMs and ran the delete again and that seemed to work. Note that you also need to clean up the packer images (which you will pay for).
