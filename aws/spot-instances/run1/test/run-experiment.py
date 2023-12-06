#!/usr/bin/env python3

import argparse
import copy
import json
import os
import random
import time
import sys

import metricsoperator.utils as utils
from metricsoperator import MetricsOperator
from kubescaler.scaler.aws import EKSCluster

# import the script we have two levels up
here = os.path.abspath(os.path.dirname(__file__))
root = os.path.dirname(here)

# Add the spot_instances library to the path
sys.path.insert(0, root)

templates = os.path.join(here, "metrics")
lammps_template = utils.read_file(os.path.join(templates, "mpitrace-lammps.yaml"))
hwloc_template = utils.read_file(os.path.join(templates, "hwloc.yaml"))

# Hotplug script!
hotplug = "https://gist.githubusercontent.com/vsoch/467467cacf32bdc2303af5e3534311b8/raw/9329d7014ec5c5dabf754d9186d49d602afc97c0/hotplug.sh"

# Keep a cache of current nodes we know about, and creation / removal times
cli = None
history = {}

# This data file must exist, it has a full price table
data_file = os.path.join(root, "instances-aws.csv")

oras_user = os.environ.get("ORAS_USER")
oras_pass = os.environ.get("ORAS_PASS")
if not oras_user or not oras_pass:
    sys.exit(
        "Please export ORAS_USER and ORAS_PASS to the environment, will be used for push secret."
    )


import spot_instances as spot_cli  # noqa

# Exit early if we haven't generated the data
if not os.path.exists(data_file):
    sys.exit(f"Cannot find {data_file}! Run spot_instances.py gen first.")

# TODO: should we select instances with memory within some range of one another?
# Remember you can filter instances before running this:
# python spot_instances.py select --min-vcpu 128 --max-vcpu 128 --number 20
experiment_plans = [
    {
        "vcpu": 32,
        "name": "4x32vcpu",
        "max-instance-types": 4,
        "filter-instance-types": 20,
        "max-spot-price": 2,
        # Subs / variables for this problem size.
        # We aren't setting memory because all the spot instances are different
        "lammps": {
            "[[CPU]]": 10,
            "[[X]]": 2,
            "[[Y]]": 2,
            "[[Z]]": 2,
            "[[NP]]": 16,
        },
    },
    {
        "cores": 128,
        "name": "6x128cores",
        "max-instance-types": 4,
        "filter-instance-types": 20,
        "max-spot-price": 10,
        "lammps": {
            # CPU is setting the resource limit/request
            "[[CPU]]": 120,
            "[[X]]": 64,
            "[[Y]]": 16,
            "[[Z]]": 16,
            # This is going to lammps (lmp)
            "[[NP]]": 128,
        },
    },
]


def get_parser():
    parser = argparse.ArgumentParser(
        description="Spot Instance Experiment Running",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--data-dir",
        help="path to save data",
        default=os.path.join(here, "data"),
    )
    parser.add_argument(
        "-n",
        "--name",
        help="select one or more experiments by name",
        action="append",
    )
    parser.add_argument(
        "--iters",
        help="iterations of lammps to run per cluster (set to 1 for testing)",
        type=int,
        default=1,
    )
    parser.add_argument(
        "--batches",
        help="batches (number of selections of instance types) for one subset (set to 1 for testing)",
        type=int,
        default=1,
    )
    parser.add_argument(
        "--sleep",
        help="seconds to sleep to allow for container pulls",
        type=int,
        default=40,
    )
    parser.add_argument(
        "--hypervisor",
        help="filter to this hypervisor",
        default="nitro",
    )
    parser.add_argument(
        "--keypair-file",
        help="keypair file to create or use (required)",
    )
    parser.add_argument(
        "--keypair-name",
        help="keypair name to create or use (required)",
    )
    parser.add_argument(
        "--bare-metal",
        help="select bare metal instances",
        default=False,
        action="store_true",
    )
    parser.add_argument(
        "--has-gpu",
        help="select GPU instances",
        default=False,
        action="store_true",
    )
    parser.add_argument(
        "--cluster-name",
        help="cluster name to use (defaults to spot-instance-testing-cluster",
        default="spot-instance-testing-cluster",
    )
    parser.add_argument(
        "--arch",
        help="architecture to select (defaults to x86_64",
        default="x86_64",
    )

    # This is hard coded to 8 for a consistent size run of LAMMPS
    parser.add_argument(
        "--nodes",
        help="number of spot instances (and nodes) to request.",
        type=int,
        default=8,
    )
    return parser


# Here we want to check:
# 1. monitor for new nodes
# 2. update threading on new nodes
# 3. check for nodes to be ready, pause starts if not
# 4. save data that estimates when they are there / gone

# I originally used a thread but it worked very poorly.


def monitor_nodes(count, outdir, instances):
    """
    Monitor nodes, ensuring that they have hyperthreading disabled.
    Also keep track of when they go up / down (so we get a sense
    of how quickly a spot is around).

    count: the number that should be running.
    outdir: the directory to write data
    instances: instance list that are multi threaded
    """
    global cli
    global history

    # Output file to write results to
    outfile = os.path.join(outdir, "spot-instance-activity.json")

    # Keep running, check every 15 seconds
    k8s = cli.get_k8s_client()

    # Updated list of nodes seen
    seen = set()

    # Make a count of nodes ready
    for node in k8s.list_node().items:
        name = node.metadata.name

        # Ignore the sticky node
        if "sticky" in node.metadata.labels:
            continue
        instance_type = node.metadata.labels["beta.kubernetes.io/instance-type"]

        # If the instance isn't in our current cache, it's new!
        if name not in history:
            # I don't see why we can't update hyperthreading before ready (but should check this)
            history[name] = {"noticed_appearance_time": time.time()}

            # Only disable hyperthreading if we need to :)
            if instance_type in instances:
                print(
                    f"🥸️ New node added to cluster {name}, disabling hyper-threading."
                )
                disable_instance_hyperthreading(instance_type, name)
            else:
                print(f"🥸️ New node added to cluster {name}.")
        seen.add(name)

    # Now go through cache, nodes that aren't in seen were removed
    for name in history:
        if name not in seen:
            print(f"🥸️ Node {name} has dissappeared from cluster.")
            now = time.time()
            history[name]["noticed_disappeared_time"] = now
            history[name]["elapsed_time"] = (
                now - history[name]["noticed_appearance_time"]
            )

    # Save data on each pass
    utils.write_json(history, outfile)


class Experiment:
    """
    An Experiment holds a set of parameters and handles load, save, etc.
    """

    def __init__(
        self,
        plan,
        max_instance_types=4,
        filter_instance_types=20,
        bare_metal=False,
        arch="x86_64",
        has_gpu=False,
        # Live dangerously, try different ones?
        hypervisor=None,
    ):
        self._max_instance_types = max_instance_types
        self._filter_instance_types = filter_instance_types
        self.hypervisor = hypervisor
        self.bare_metal = bare_metal
        self.has_gpu = has_gpu
        self.arch = arch
        self.load(plan)

    def load(self, plan):
        """
        Load (or reload) an experiment into the class.
        """
        self.plan = plan

        # Ideally, the user provides a name. Otherwise, long UID
        # The uid just smashes all the fields together
        self.id = self.plan.get("name") or generate_uid(plan)

        # If we have a max spot price, don't set a number
        number = self.filter_instance_types if not self.max_spot_price else None

        # Note we are setting min == max to get a consistent value.
        # This generates the original filtered set to be used for batches
        self.df = spot_cli.select_instances(
            data_file,
            min_cores=self.plan["cores"],
            max_cores=self.plan["cores"],
            number=number,
            bare_metal=self.bare_metal,
            max_spot_price=self.max_spot_price,
            hypervisor=self.hypervisor,
            arch=self.arch,
            has_gpu=self.has_gpu,
        )

    def __repr__(self):
        return str(self)

    def __str__(self):
        return f"{self.id}.Experiment"

    @property
    def max_instance_types(self):
        return self.plan.get("max-instance-types") or self._max_instance_types

    @property
    def filter_instance_types(self):
        return self.plan.get("filter-instance-types") or self._filter_instance_types

    @property
    def max_spot_price(self):
        return self.plan.get("max-spot-price")

    def save_filtered(self, path):
        """
        Save data frame to file
        """
        self.df.to_csv(path)

    def export(self):
        """
        Export experiment metadata
        """
        return {
            "runs": [],
            "plan": self.plan,
            "filter_instance_types": self.filter_instance_types,
            "max_instance_types": self.max_instance_types,
            "max_spot_price": self.max_spot_price,
            "bare_metal": self.bare_metal,
            "arch": self.arch,
            "has_gpu": self.has_gpu,
        }

    @property
    def filtered(self):
        """
        Show the number of instances filtered
        """
        return self.df.shape[0]

    def select_machine_types(self, count):
        """
        Generate an experiment by randomly selecting from the instances

        We always choose randomly here.
        """
        listing = list(self.df.instance.values)
        random.shuffle(listing)
        selected = listing[:count]
        subset = self.df[self.df.instance.isin(selected)]
        show_selected(subset)
        return subset


def show_selected(df):
    """
    Given a selected dataframe, show it (and the price)
    """
    print("\n✅️ Selected instances")
    print(df)
    print("\n✅️ Mean (std) of spot price")
    mean = round(df.spot_price.mean(), 2)
    std = round(df.spot_price.std(), 2)
    print(f"${mean} (${std})")


def read_json(filename):
    """
    Read json from file.
    """
    with open(filename, "r") as fd:
        content = json.loads(fd.read())
    return content


def confirm_action(question):
    """
    Ask for confirmation of an action
    """
    response = input(question + " (yes/no)? ")
    while len(response) < 1 or response[0].lower().strip() not in "ynyesno":
        response = input("Please answer yes or no: ")
    if response[0].lower().strip() in "no":
        return False
    return True


def plan_experiments(args):
    """
    Given experiment "plans" create a matrix of actual experiments (and instance types) to run
    """
    experiments = {}
    # Were we given a plan in json?

    for plan in experiment_plans:
        # The user can select an experiment by name
        if args.name and plan["name"] not in args.name:
            continue

        print(f"🧪️ Planning experiments for {plan}")
        exp = Experiment(
            plan,
            bare_metal=args.bare_metal,
            arch=args.arch,
            has_gpu=args.has_gpu,
            hypervisor=args.hypervisor,
        )

        # Save us from ourselves, don't repeat an experiment
        if exp.id in experiments:
            continue

        # No instances available
        if exp.filtered == 0:
            print(f"📛️ WARNING: {exp.id} selected no instances, and cannot be run.")
            continue

        experiments[exp.id] = exp
    return experiments


def generate_uid(params):
    """
    Generate a unique id based on params.
    """
    uid = ""
    for k, v in params.items():
        if not isinstance(v, dict):
            uid += k.lower() + "-" + str(v).lower()
        else:
            uid += k.lower()
    return uid


def write_json(obj, filename):
    """
    write json to output file
    """
    with open(filename, "w") as fd:
        fd.write(json.dumps(obj, indent=4))


def create_template(tag, template, replaces):
    """
    Generate the lammps templated yaml, filling in size and number of processes
    """
    templated = template
    for k, v in replaces.items():
        templated = templated.replace(k, str(v))
    return templated


def run_hwloc(exp, args, batch, data_path):
    """
    Run hwloc on unique machines (that we haven't seen yet).

    We run on all machines to make life easy, but only save ones we
    have not seen yet.
    """
    global cli
    # The node must be selected and correspond with a tag for metadata
    # We can use the label "node.kubernetes.io/instance-type" == instance type to select
    # then run one per machine type (with corresponding tag that includes hwloc-machine type and expid)
    # "[[MACHINE]]" should be the selector, and the label should be node.kubernetes.io/instance-type: [[MACHINE]]
    # Get nodes (to see unique). Let's compare what the kubelet sees to hwloc
    unique_machines = {}
    k8s = cli.get_k8s_client()
    for node in k8s.list_node().items:
        if "node.kubernetes.io/instance-type" not in node.metadata.labels:
            print("Warning: we are not running on a production cluster.")
            break

        machine_type = node.metadata.labels["node.kubernetes.io/instance-type"]
        if machine_type in unique_machines:
            continue
        unique_machines[machine_type] = {
            "labels": node.metadata.labels,
            "name": node.metadata.name,
            "capacity": node.status.capacity,
            "info": node.status.node_info.to_dict(),
            "allocatable": node.status.allocatable,
        }

    for machine_type, meta in unique_machines.items():
        print(f"🤖️ Running hwloc for machine type {machine_type}...")
        replaces = {"[[MACHINE]]": machine_type, "[[TAG]]": batch}
        templated = create_template(batch, hwloc_template, replaces)
        metrics_yaml = os.path.join(data_path, f"hwloc-{batch}.yaml")
        utils.write_file(templated, metrics_yaml)

        # This one self-cleans up, wait until it's completed
        try:
            run_kubectl(f"apply -f {metrics_yaml}")
            m = MetricsOperator(metrics_yaml)
            name = m.spec["metadata"]["name"]
            run_kubectl(f"wait --for=condition=complete job/{name}-m-0")
            run_kubectl(f"delete -f {metrics_yaml} --wait=true")
        except:
            print("Issue with running hwloc! Interactively debug.")
            import IPython

            IPython.embed()
            sys.exit()

    return unique_machines


def run_lammps(exp, args, batch, data_path, multi_threaded):
    """
    Run LAMMPS for some number of iterations
    """
    global cli

    replaces = exp.plan["lammps"]
    replaces["[[NODES]]"] = args.nodes

    # Keep total wrapped times (not wall times)
    wrapped_times = {}

    # Create a metrics yaml directory for the experiment
    metrics_dir = os.path.join(data_path, "metrics")
    if not os.path.exists(metrics_dir):
        os.makedirs(metrics_dir)

    # Keep track of those that were killed (in testing, I lost a spot node)
    killed = []

    # Now run lammps some number of times.
    for i in range(3, args.iters):
        # Check for new spot instances each time
        monitor_nodes(args.nodes, data_path, multi_threaded)
        run_kubectl("get nodes")

        print(f"🪔️ Running iteration {i} of LAMMPS")

        # Tag must be unique for batch and iteration
        tag = f"iter-{batch}-{i}"

        # These are determined by the iteration
        subs = copy.deepcopy(replaces)
        subs["[[TAG]]"] = tag
        templated = create_template(tag, lammps_template, subs)
        metrics_yaml = os.path.join(metrics_dir, f"lammps-{tag}.yaml")
        utils.write_file(templated, metrics_yaml)

        # Cheat and update the kubeconfig-aws.yaml
        m = MetricsOperator(metrics_yaml)
        m.load_kube_config(cli.kube_config_file)

        # Ensure we catch any errors, wrap entire thing!
        try:
            start_time = time.time()
            lammps_single_run(i, args, killed, data_path, metrics_yaml)
            end_time = time.time()
            total = end_time - start_time
            print(f"Single run took {total} seconds.")
            wrapped_times[tag] = total
        except:
            print(f"Issue running iteration {i}, interactively debug.")
            import IPython

            IPython.embed()

    return {"wrapped_times": wrapped_times, "iters_killed": killed}


def lammps_single_run(i, args, killed, data_path, metrics_yaml):
    """
    Wrap the entire lammps run to absolutely catch any issues.
    """
    global cli

    run_kubectl(f"apply -f {metrics_yaml}")
    m = MetricsOperator(metrics_yaml)
    name = m.spec["metadata"]["name"]
    time.sleep(10)
    run_kubectl(f"wait --for=condition=complete --timeout=600s job/{name}-l-0")

    # Need to better expose this
    metric = m.get_parser()
    metric._core_v1 = cli.get_k8s_client()
    pods = metric.get_pods()

    # First pod always the launcher (l > w)
    launcher = pods.items[0].metadata.name
    metric._core_v1 = cli.get_k8s_client()
    lines = metric.stream_output(
        name=launcher, namespace=metric.namespace, container="launcher"
    )

    if "KILLED" in lines and "BAD TERMINATION" in lines:
        print(f"Iteration {i} was killed or not successful.")
        killed.append(i)

    # Keep a backup of the logfile
    logfile = os.path.join(data_path, f"lammps-{i}.log")
    utils.write_file(lines, logfile)

    # Also save node metadata for this run
    response = metric.core_v1.list_node(_preload_content=False)
    nodes = json.loads(response.data)
    nodefile = os.path.join(data_path, f"nodes-{i}.json")
    utils.write_json(nodes, nodefile)

    # Wait for all pods to terminate
    # I am being lazy, we have a function but... but... but... :)
    # metric.wait_for_delete(pod_prefix=metric.name)
    run_kubectl(f"delete -f {metrics_yaml} --wait=true", allow_fail=True)


def describe_instances_topology():
    """
    Get the topology for the instance types we have chosen.

    We originally wanted to use the topology API here, but it's limited. :/
    """
    global cli
    k8s = cli.get_k8s_client()

    # We need instance ids, organized by zone (AvailabilityZone)
    instances = []
    for node in k8s.list_node().items:
        instance_type = node.metadata.labels["beta.kubernetes.io/instance-type"]
        zone = node.metadata.labels["topology.kubernetes.io/zone"]
        region = node.metadata.labels["topology.kubernetes.io/region"]
        instances.append(
            {
                "type": instance_type,
                "zone": zone,
                "region": region,
                "name": node.metadata.name,
            }
        )

    # Note that topology is limited in instance types, not going to get hits here
    # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2/client/describe_instance_topology.html
    return instances


def run_kubectl(command, allow_fail=False):
    """
    Wrapper to client to run command with kubeconfig file
    """
    global cli
    command = f"kubectl --kubeconfig={cli.kube_config_file} {command}"
    res = os.system(command)
    if res != 0 and not allow_fail:
        print(
            f"ERROR: running {command} - debug and ensure it works before exiting from session."
        )
        import IPython

        IPython.embed()
    return res


def install_operators(allow_fail=False):
    """
    Install all needed operators to the spot cluster

    Also create the registry (just an admission webnhook) and secret for it.
    """
    global cli
    # This is cheating a bit :)
    # But it's easier than programmatically

    # JobSet needs to be applied server side, otherwise error about annotations
    filename = os.path.join(root, "crd", "jobset-operator.yaml")
    run_kubectl(f"apply --server-side -f {filename}", allow_fail=allow_fail)
    time.sleep(5)

    # Metrics Operator
    filename = os.path.join(root, "crd", "metrics-operator.yaml")
    run_kubectl(f"apply -f {filename}", allow_fail=allow_fail)
    time.sleep(2)
    filename = os.path.join(root, "crd", "cert-manager.yaml")
    run_kubectl(f"apply -f {filename}", allow_fail=allow_fail)

    # Oras operator needs to pause for cert manager
    time.sleep(10)
    filename = os.path.join(root, "crd", "oras-operator.yaml")
    run_kubectl(f"apply -f {filename}", allow_fail=allow_fail)

    ## Registry (no pod deployed)
    filename = os.path.join(root, "crd", "oras.yaml")
    run_kubectl(f"apply -f {filename}", allow_fail=allow_fail)
    generate_secret()
    run_kubectl("get pods --all-namespaces -o=wide")


def generate_secret():
    """
    Generate the secret (without running into a really long line!)
    """
    global cli
    # Finally, create the secret. This one is long (and there is trouble) so let's write to file
    content = f"""#!/bin/bash
kubectl --kubeconfig={cli.kube_config_file} create secret generic oras-env \\
    --from-literal="ORAS_USER={oras_user}" \\
    --from-literal="ORAS_PUSH_PASS={oras_pass}" \\
    --from-literal="ORAS_PULL_PASS={oras_pass}"
"""
    utils.write_file(content, "create_secret.sh")
    os.system("/bin/bash ./create_secret.sh")
    os.remove("create_secret.sh")


def check_nodes_ready(args):
    """
    check that nodes are ready.

    We do this extra check because the kubescaler function assumes N nodes,
    and this would include our sticky node (one more)
    """
    import IPython

    IPython.embed()
    return
    start = time.time()
    kubectl = cli.get_k8s_client()
    while True:
        print(f"⏱️  Waiting for {self.node_count} nodes to be Ready...")
        time.sleep(5)
        nodes = kubectl.list_node()
        ready_count = 0
        for node in nodes.items:
            for condition in node.status.conditions:
                if "sticky" in node.metadata.labels:
                    continue

                # Don't add to node ready count if not ready
                if condition.type == "Ready" and condition.status == "True":
                    ready_count += 1
        if ready_count >= args.nodes:
            break
    print(f"Time for kubernetes to get nodes - {time.time()-start}")
    return ready_count


def create_persistent_node():
    """
    Create a 'sticky-node' that will run persistently to install operators to.

    We also want to label it to easily skip it in the future parsing.
    """
    global cli
    k8s = cli.get_k8s_client()

    node_group = cli.create_nodegroup(
        # About $1.5/hour on demand, 32 vCPU, nitro
        machine_types=["m5.8xlarge"],
        node_group_name="sticky-node",
        min_nodes=1,
        max_nodes=1,
        node_count=1,
        capacity_type="ON_DEMAND",
    )

    # Install the operators to it.
    # We do this before creating the spot group so it hits our sticky note!
    install_operators()

    # Label our sticky node so we can easily skip it.
    print("🏷️  Labeling the sticky-node so we find it in the future!")
    for node in k8s.list_node().items:
        run_kubectl(f"label nodes {node.metadata.name} sticky=yes")
    return node_group


def disable_instance_hyperthreading(instance_type, name):
    """
    Function to disable hyperthreading for a named instance
    """
    global cli
    k8s = cli.get_k8s_client()  # noqa
    print(f"Disabling hyperthreading for {name}: {instance_type}")
    command = f"kubectl node-shell --kubeconfig={cli.kube_config_file} {name} -- wget --quiet {hotplug};"
    os.system(command)
    command = f"kubectl node-shell --kubeconfig={cli.kube_config_file} {name} -- bash ./hotplug.sh"
    os.system(command)
    command = f"kubectl node-shell --kubeconfig={cli.kube_config_file} {name} -- lscpu --extended"
    os.system(command)


def run_experiments(experiments, args, data_dir):
    """
    Wrap experiment running separately in case we lose spot nodes and can recover
    """
    global cli

    # Use kubescaler ekscluster to create the cluster
    # We will request / delete nodegroups with spot from it
    cli = EKSCluster(
        name=args.cluster_name,
        eks_nodegroup=True,
        capacity_type="SPOT",
        node_count=args.nodes,
        min_nodes=args.nodes,
        max_nodes=args.nodes,
        keypair_name=args.keypair_name,
        keypair_file=args.keypair_file,
    )

    # Note we are NOT creating the node group here - just the cluster, so machine types aren't relevant
    # We will add machine types as node groups (to create and delete from the cluster) later

    cli.create_cluster(create_nodes=False)
    original_times = copy.deepcopy(cli.times)

    # The keyfile file must exist otherwise ssh won't work.
    if not os.path.exists(args.keypair_file):
        print(
            "WARNING: keypair file {keypair_file} does not exist! Did you choose someone else's?"
        )
        print(
            "If you need this for ssh: cli.delete_cluster() and select new name or existing name/file."
        )

    # At this point we have a control plane. We are going to be creating a managed node group of spot,
    # but we also need a persistent node group for the operator installs, ON_DEMAND.
    persistent_node_group = create_persistent_node()

    # Note that the experiment already has a table of values filtered down
    # Each experiment has some number of batches (we will typically just run one experiment)
    for name, exp in experiments.items():
        print(
            f"== Experiment {exp.id} has {exp.filtered} filtered instances to select from for each batch."
        )

        # Save the entire table just once
        path = os.path.join(data_dir, exp.id)
        if not os.path.exists(path):
            os.makedirs(path)
        exp.save_filtered(os.path.join(path, "filtered-instances.csv"))

        # These are all instance types that have > 1 thread by default
        multi_threaded = exp.df.instance[exp.df.threads_per_core > 1].tolist()

        # For each of N (20) batches:
        for batch in range(args.batches):
            # create an output directory for the experiment and batch
            outdir = os.path.join(data_dir, exp.id, str(batch))
            if not os.path.exists(outdir):
                print(f"Creating output directory {outdir}")
                os.makedirs(outdir)

            # Reset times between experiments (we saved original times already)
            cli.times = {}

            # Here we select our random machine types from the set (this shows/prints it too)
            # This returns a subset of the data frame. The entire experiment df is saved with experiment
            # Randomly select from the filtered set AND give to the AWS API to create N nodes
            subset = exp.select_machine_types(exp.max_instance_types)
            machine_types = list(subset.instance.values)

            # Now create the node groups!
            # This is N nodes for some unique set of instances from the original filtered set
            cli.create_cluster_nodes(machine_types)

            # One more sanity check that nodes ready
            check_nodes_ready(args)

            # Add cluster times to the new times
            times = copy.deepcopy(original_times)
            times.update(cli.times)

            # A new result object for each. Runs results go into the registry
            result = {
                "name": name,
                "times": times,
                "nodes": args.nodes,
                "cluster_name": args.cluster_name,
                "metadata": exp.export(),
                "machine_types": machine_types,
                "mean_price": subset.price.mean(),
                "std_price": subset.price.std(),
                "selected_for_request": subset.to_dict(orient="records"),
            }
            # Get topology
            topology = describe_instances_topology()
            result["topology"] = topology

            # EXPERIMENTS: ---
            # Run LAMMPS 20x, collect MPI trace too, lstopo and the AWS topology API
            # Run lammps - results are saved to the OCI registry
            result["lammps"] = run_lammps(exp, args, batch, outdir, multi_threaded)

            # Get hwloc files for unique nodes. I am aware there could be
            # overlap between experiments, but I think we should sanity check
            # that the instance type nodes are actually equivalent. The cluster
            # we have here might also not == the lammps runs, but we do our best
            unique_machines = run_hwloc(exp, args, batch, outdir)
            outfile = os.path.join(outdir, "hwloc-unique-machines-nodes.json")
            write_json(unique_machines, outfile)

            # Show and save results
            print(json.dumps(result))
            outfile = os.path.join(outdir, "result.json")
            write_json(result, outfile)

            # And now... delete it! We don't need it, lol
            cli.delete_nodegroup(cli.node_group_name)

    print("Experiments are done! Next, use ORAS to pull artifacts.")

    # When we are done, delete the sticky node cluster
    cli.delete_nodegroup(persistent_node_group["nodegroup"]["nodegroupName"])
    cli.delete_cluster()


def main():
    """
    Run experiments for lammps, and collect hwloc info.
    """
    parser = get_parser()

    # If an error occurs while parsing the arguments, the interpreter will exit with value 2
    args, _ = parser.parse_known_args()

    if not args.keypair_name or not args.keypair_file:
        sys.exit(
            "A keypair name and file are required for the experiment (created if do not exist)"
        )

    if not os.path.exists(args.data_dir):
        os.makedirs(args.data_dir)

    # plan experiments!
    experiments = plan_experiments(args)
    print("🧪️ Experiments:")
    for exp in experiments:
        print(f"   {exp}")

    print("🪴️ Planning to run:")
    print(f"   Cluster name        : {args.cluster_name}")
    print(f"     keypair-name      : {args.keypair_name}")
    print(f"     keypair-file      : {args.keypair_file}")
    print(f"   Output Data         : {args.data_dir}")
    print(f"   Experiments         : {len(experiments)}")
    print(f"     bare-metal        : {args.bare_metal}")
    print(f"     nodes             : {args.nodes}")
    print(f"   Batches             : {args.batches}")
    print(f"     iterations/batch  : {args.iters}")
    if not confirm_action("Would you like to continue?"):
        sys.exit("📺️ Cancelled!")

    # Main experiment running, show total time just for user FYI
    start_experiments = time.time()
    run_experiments(experiments, args, args.data_dir)
    stop_experiments = time.time()
    total = stop_experiments - start_experiments
    print(f"total time to run is {total} seconds")


if __name__ == "__main__":
    main()
