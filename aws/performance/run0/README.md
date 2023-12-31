# Performance Testing

We want to be able to run an application (e.g., LAMMPS) and also collect metrics about performance and the results, and easily save all of these things. This is a prototype for what that might look like.

 - [The Metrics Operator](https://github.com/converged-computing/metrics-operator) can run the application LAMMPS along with assessments of it (the metrics).
 - [The ORAS Operator](https://github.com/converged-computing/oras-operator) can keep a local cache of results to pull from at the end.
 
# Usage

This setup will test running different experiments with the metrics operator, and specifically those that generate output files,
and using the ORAS operator to push and save them to a local registry. We will be changing the default watched object from "pod" to
"job."

## Cluster

First, create a test cluster.

```bash
kind create cluster --config ./kind-config.yaml
```

Note that I struggled with creating ingress for a while because Kind needs additions for it to work (in that file).
Install the metrics operator and oras operator:

```bash
# The Metrics Operator requires JobSet
VERSION=v0.2.1
kubectl apply --server-side -f https://github.com/kubernetes-sigs/jobset/releases/download/$VERSION/manifests.yaml
kubectl apply -f https://raw.githubusercontent.com/converged-computing/metrics-operator/main/examples/dist/metrics-operator.yaml

# The oras operator requires cert manager (wait a minute or so for this to be ready)
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.1/cert-manager.yaml

# Wait about a minute...
kubectl apply -f https://raw.githubusercontent.com/converged-computing/oras-operator/main/examples/dist/oras-operator.yaml
```

## Registry

Create the registry, which is called "oras" - our pods will need to have this annotation to use it.

```bash
kubectl apply -f oras.yaml
```

Now we have the metrics operator and oras operator running in the same namespace! Let's run an experiment that will save several artifacts for us. Since we get to decide the organization and naming of the artifacts, we can take a simple approach of having each named based on the metric (the repository of the registry). Specifically, for experiments we will:

 - run lammps with output alongside it from mpitrace
 - run hwloc on our nodes

This means we will have two output files from hwloc (png and xml), a lammps log (text), and several trace files (mpitrace). 

## Testing

To test:

```bash
kubectl apply -f ./metrics/test/hwloc-iter-0.yaml  
kubectl apply -f ./metrics/test/lammps-iter-0.yaml
```

You should see the lammps run and the registry push in logs.

```bash
kubectl logs lammps-0-l-0-0-7ppcg -c launcher
kubectl logs lammps-0-l-0-0-7ppcg -c oras
```

Same for hwloc

```bash
kubectl logs hwloc-0-m-0-0-nh66b
```

Try pulling the output for each. Here is how to do a simple port-forward (works for small artifacts):

```bash
# Do this in a different terminal
kubectl port-forward oras-0 5000:5000
```

Then pull

```bash
cd metrics/test
oras pull localhost:5000/metric/lammps-test:iter-0 --insecure
oras pull localhost:5000/metric/hwloc-test:iter-0 --insecure
```

This will pull the HNS (lammps) and analysis (hwloc) results.
Now that we are sure the data is there, we can delete everything.

```bash
cd ../../
kubectl delete -f ./metrics/test/
```

## HPCToolkit

We can test running hpctoolkit to generate larger artifacts, and then use a proper ingress to
download from the registry. After creating the cluster, apply the hpctoolkit yaml:

```bash
kubectl apply -f metrics/test/hpctoolkit-iter-0.yaml
```

### Ingress

We then want to create a service to access the registry (make sure to close the port forward):

```bash
kubectl apply -f metrics/ingress.yaml
```
```console
$ kubectl describe ingress
Name:             oras-ingress
Labels:           <none>
Namespace:        default
Address:          
Ingress Class:    <none>
Default backend:  <default>
Rules:
  Host        Path  Backends
  ----        ----  --------
  localhost   
              /   oras-service:5000 (10.244.0.12:5000)
Annotations:  <none>
Events:       <none>
```

We are then going to apply [ingress-nginx](https://kind.sigs.k8s.io/docs/user/ingress/#ingress-nginx).

```
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml
kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=90s
```

To then pull:

```bash
oras repo list localhost:5000
```
```console
$ oras repo list localhost
metric/hpctoolkit-test

$ oras repo tags localhost/metric/hpctoolkit-test
iter-2
```

Try pulling the chonker!

```bash
oras pull localhost/metric/hpctoolkit-test:iter-2 --insecure -o ./metrics/test/hpctoolkit.tar.gz
```

## Experiments

Now let's run the full experiments, which can be totally automated now with the ORAS oci registry.

```bash
python run-experiment.py --iters 5 --sleep 5
```

And then you can port forward again or (suggested) use the [ingress](#ingress) approach and pull. You'll need to be sure to put the different tags in separate result directories, etc.

```
mkdir -p results
cd results
```

Note that for port-forward you need to target `localhost:5000`.

```console
root=$(pwd)
for repo in $(oras repo ls localhost --insecure); do
    echo "Pulling artifacts for repository ${repo}"
    for tag in $(oras repo tags localhost/${repo} --insecure); do
       uri=${repo}:${tag}       
       echo "Pulling URI ${uri}"
       mkdir -p ${repo}/${tag}
       cd ${repo}/${tag}
       oras pull localhost/${uri} --insecure -o results.tar.gz
       if [[ $repo == *"hpctoolkit"* ]]; then
           echo "We will not extract hpctoolkit"
       else
           echo "Extracting result for ${uri}"
           tar -xzvf results.tar.gz
           rm results.tar.gz
       fi
       cd $root
    done
done
```

This should give a full directory of results (this was just for one iteration, so a smaller view):

```console
metric/
├── hwloc
│   └── iter-0
│       └── analysis
│           ├── architecture.png
│           └── machine.xml
├── hwloc-test
│   └── iter-0
│       └── analysis
│           ├── architecture.png
│           └── machine.xml
├── lammps
│   └──iter-0
│       └── HNS
│           ├── data.hns-equil
│           ├── ffield.reax.hns
│           ├── hostlist.txt
│           ├── in.reaxc.hns
│           ├── lammps.out
│           ├── log.8Mar18.reaxc.hns.g++.1
│           ├── log.8Mar18.reaxc.hns.g++.4
│           ├── log.lammps
│           ├── mpi_profile.105.0
│           ├── mpi_profile.105.1
│           ├── mpi_profile.105.2
│           ├── oras-run-application.sh
│           ├── problem.sh
│           └── README.txt
│    
│
└── lammps-test
    └── iter-0
        └── HNS
            ├── data.hns-equil
            ├── ffield.reax.hns
            ├── hostlist.txt
            ├── in.reaxc.hns
            ├── lammps.out
            ├── log.8Mar18.reaxc.hns.g++.1
            ├── log.8Mar18.reaxc.hns.g++.4
            ├── log.lammps
            ├── mpi_profile.107.0
            ├── mpi_profile.107.1
            ├── mpi_profile.107.2
            ├── oras-run-application.sh
            ├── problem.sh
            └── README.txt

17 directories, 36 files
```

Note that we have results for hpctoolkit that aren't extracted (or added to this repo):

```
metric/
├── hpctoolkit-test
│   ├── iter-0
│   │   └── results.tar.gz
│   ├── iter-1
│   │   └── results.tar.gz
│   ├── iter-2
│   │   └── results.tar.gz
│   ├── iter-3
│   │   └── results.tar.gz
│   └── iter-4
│       └── results.tar.gz
```

Neat! So we can run that for more iterations, and even different metrics, and we should be able to automate the entire thing and save results. The yaml files you generated are in [data](data) and the results in [results](results) and templates in [metrics](metrics).

## Clean Up

When you are done, clean up.

```bash
kind delete cluster
```
