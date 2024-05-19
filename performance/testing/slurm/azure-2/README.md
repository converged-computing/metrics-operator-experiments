# CycleCloud + Slurm

This is the third (maybe 4th) attempt to deploy CycleCloud with Slurm on Azure.
I am going to try [these steps](https://tsi-ccdoc.readthedocs.io/en/master/Tech-tips/HPC-with-Azure-CycleCloud.html) that
do two things differently:

1. Create the auth credentials on the command line.
2. Deploy a VM with CycleCloud to start.

Let's pray this works. Really, really. 🙏️😆️

```
az account set --subscription "<subscription_id>
az ad sp create-for-rbac --role contributor --scopes="/subscriptions/<subscription-id>"
```

Note that I had to tweak the instruction above from the docs - the one they provided didn't work.
Save the output under role.json (don't add to git I think)
List locations and create a resource group in a location:

```
az group create --name slurmy --location westus
```

```bash
# If you need to get locations
 az account list-locations
```

Create vnet and subnet

```bash
az network vnet create --name slurmy --resource-group slurmy --address-prefix 10.0.0.0/16
az network vnet subnet create --resource-group slurmy --vnet-name slurmy --name compute --address-prefix 10.0.0.0/22
```

Try this now?

```
FQDN=cyclecloud.westus.azurecontainer.io 
CIName=slurmy
Location=westus
az container create \
  --resource-group ${CIName} \
  --location ${Location} \
  --name ${CIName} \
  --dns-name-label ${CIName} \
  --image mcr.microsoft.com/hpc/azure-cyclecloud \
  --ip-address public \
  --ports 80 443 \
  --cpu 2 \
  --memory 4 \
  -e JAVA_HEAP_SIZE=2048 FQDN="${FQDN}"
```

That will generate a message in the terminal to log into your cluster name e.g., `https://slurmy.westus.azurecontainer.io` and then you'll need to login, provide the credentials you saved to role.json, and create the slurm cluster.
