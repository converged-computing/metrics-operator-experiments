#!/usr/bin/env python3

import argparse
import copy
import json
import os
import random
import sys
import time

from metricsoperator import MetricsOperator
import metricsoperator.metrics as mutils
from kubescaler.scaler.aws import EKSCluster

# import the script we have two levels up
here = os.path.abspath(os.path.dirname(__file__))

# This data file must exist, it has a full price table
data_file = os.path.join(here, "instances-aws.csv")

import spot_instances as spot_cli  # noqa

# Exit early if we haven't generated the data
if not os.path.exists(data_file):
    sys.exit(f"Cannot find {data_file}! Run spot_instances.py gen first.")

# This template will be populated with number of spot nodes
# This is hard coded for 32vCPU, np will be pods * 12
lammps_template = """
apiVersion: flux-framework.org/v1alpha2
kind: MetricSet
metadata:
  labels:
    app.kubernetes.io/name: metricset
    app.kubernetes.io/instance: metricset-sample
  name: metricset-sample
spec:
  pods: [[SIZE]]
  metrics:
   - name: app-lammps
     options:
       command: mpirun --hostfile ./hostlist.txt -np [[NP]] -ppn 12 lmp -v x 16 -v y 8 -v z 8 -in in.reaxc.hns -nocite
       soleTenancy: "true"
     # 32 vCPU == 16 CPU so a limit of 12 is reasonable
     resources:
       limits:       
         cpu: 12
       requests:
         cpu: 12
"""

# This is quasi manual, we need to add a volume to actually persist the data. We will copy for now.
hwloc_template = """
apiVersion: flux-framework.org/v1alpha2
kind: MetricSet
metadata:
  labels:
    app.kubernetes.io/name: metricset
    app.kubernetes.io/instance: metricset-sample
  name: metricset-sample
spec:
  pods: [[SIZE]]
  logging:
    interactive: true
  metrics:
    - name: sys-hwloc      
      # These are the default and do not need to be provided
      listOptions:
        commands:
          - lstopo architecture.png
          - hwloc-ls machine.xml
"""


def get_parser():
    parser = argparse.ArgumentParser(
        description="Spot Instance Experiment Running",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--max-instance-types",
        help="maximum instance types to select from (if not set in experiment plan)",
        type=int,
        default=10,
    )
    parser.add_argument(
        "--iters",
        help="iterations of lammps to run per cluster",
        type=int,
        default=10,
    )
    parser.add_argument(
        "--data-dir",
        help="path to save data",
        default=os.path.join(here, "data"),
    )
    parser.add_argument(
        "--cluster-name",
        help="cluster name to use (defaults to spot-instance-testing-cluster",
        default="spot-instance-testing-cluster",
    )
    parser.add_argument(
        "--min-spot-request",
        help="smallest number of instances to test requesting for spot",
        type=int,
        default=2,
    )
    parser.add_argument(
        "--max-spot-request",
        help="largest number of instances to test requesting for spot",
        type=int,
        default=4,
    )
    parser.add_argument(
        "--plan",
        help="plan (json) file to parse",
    )
    parser.add_argument(
        "--sleep",
        help="Sleep time for first LAMMPS run (to pull)",
        type=int,
        default=60,
    )
    parser.add_argument(
        "--nodes",
        help="number of nodes to request (defaults to 4 for testing)",
        type=int,
        default=4,
    )
    return parser


class Experiment:
    """
    An Experiment holds a set of parameters and handles load, save, etc.
    """

    def __init__(self, plan, max_instance_types=10):
        self.load(plan)
        self._max_instance_types = max_instance_types

    def load(self, plan):
        """
        Load (or reload) an experiment into the class.
        """
        self.plan = plan
        # The uid just smashes all the fields together
        self.id = generate_uid(plan)

        # Note we are setting min == max to get a consistent value. Arch defaults to x86_64 and gpu none
        self.df = spot_cli.select_instances(
            data_file,
            min_vcpu=self.plan["vcpu"],
            max_vcpu=self.plan["vcpu"],
            number=self.max_instance_types,
        )

    def __repr__(self):
        return str(self)

    def __str__(self):
        return f"{self.id}.Experiment"

    @property
    def max_instance_types(self):
        return self.plan.get("max-instance-types") or self._max_instance_types

    def export(self):
        """
        Export experiment metadata
        """
        return {
            "runs": [],
            "plan": self.plan,
            "instances": self.df.to_csv(),
            "max_instance_types": self.max_instance_types,
        }

    @property
    def count(self):
        """
        Show the number of instances selected.
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
    print("\n✅️ Mean (std) of price")
    mean = round(df.price.mean(), 2)
    std = round(df.price.std(), 2)
    print(f"${mean} (${std})")


def read_json(filename):
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
    print(f"Loading plans from {args.plan}")
    experiment_plans = read_json(args.plan)

    for plan in experiment_plans:
        print(f"🧪️ Planning experiments for {plan}")
        exp = Experiment(plan, max_instance_types=args.max_instance_types)

        # Save us from ourselves.
        if exp.id in experiments:
            print(
                f"📛️ WARNING: identifier {exp.id} is already present, meaning you have equivalent parameters in two experiments."
            )
            continue

        # No instances available
        if exp.count == 0:
            print(
                f"📛️ WARNING: identifier {exp.id} selected no instances, and cannot be run."
            )
            continue

        experiments[exp.id] = exp
    return experiments


def generate_uid(params):
    """
    Generate a unique id based on params.
    """
    uid = ""
    for k, v in params.items():
        uid += k.lower() + "-" + str(v).lower()
    return uid


def write_json(obj, filename):
    """
    write json to output file
    """
    with open(filename, "w") as fd:
        fd.write(json.dumps(obj, indent=4))


def write_file(content, filename):
    """
    write text to output file
    """
    with open(filename, "w") as fd:
        fd.write(content)


def create_lammps_template(pods):
    """
    Generate the lammps templated yaml, filling in size and number of processes
    """
    replaces = {"[[SIZE]]": str(pods), "[[NP]]": str(pods * 12)}
    templated = lammps_template
    for k, v in replaces.items():
        templated = templated.replace(k, v)
    return templated


def create_hwloc_template(pods):
    """
    Generate the hwloc templated yaml, filling in size.
    """
    replaces = {"[[SIZE]]": str(pods)}
    templated = hwloc_template
    for k, v in replaces.items():
        templated = templated.replace(k, v)
    return templated


def run_hwloc(pods, data_path, sleep=60):
    """
    Run hwloc
    """
    templated = create_hwloc_template(pods)
    metrics_yaml = os.path.join(data_path, f"hwloc-{pods}.yaml")
    write_file(templated, metrics_yaml)

    # Get a handle to the metrics operator
    kubeconfig = os.path.join(here, "kubeconfig-aws.yaml")
    m = MetricsOperator(metrics_yaml, kubeconfig=kubeconfig)

    # We don't have an hwloc parser, so we mostly need to wait for them to be running
    parser = mutils.get_metric()(m.spec, container_name="app", kubeconfig=kubeconfig)

    # Get nodes (to see unique). Let's compare what the kubelet sees to hwloc
    unique_machines = {}
    for node in parser.core_v1.list_node().items:
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
    print(f"🤡️ This cluster has {len(unique_machines)} unique node type(s).")

    # These are the nodes we need to find assignments to
    node_names = {x["name"]: mt for mt, x in unique_machines.items()}

    # Wait for all pods to be running
    print("🕰️ Waiting for hwloc pods to be running...")
    parser.wait(pod_prefix=m.spec["metadata"]["name"], states=["Running"])
    sleep(3)

    # Now find one pod per node.
    seen = set()
    for pod in parser.get_pods().items:
        node_assigned = pod.spec.to_dict()["node_name"]

        # If we need hwloc images / metadata but haven't gotten it yet...
        # Yeah os.system is janky.
        if node_assigned in node_names and node_assigned not in seen:
            machine_type = node_names[node_assigned]
            machine_xml = os.path.join(data_path, f"machine-{machine_type}.xml")
            machine_png = os.path.join(data_path, f"machine-{machine_type}.png")
            os.system(
                f"KUBECONFIG={here}/kubeconfig-aws.yaml kubectl cp {pod.metadata.name}:/machine.xml {machine_xml}"
            )
            os.system(
                f"KUBECONFIG={here}/kubeconfig-aws.yaml kubectl cp {pod.metadata.name}:/architecture.png {machine_png}"
            )
            seen.add(node_assigned)

    # When we are done, delete and return unique machines
    m.delete(pod_prefix=m.spec["metadata"]["name"])
    return unique_machines


def run_lammps(pods, iters, data_path, sleep=60):
    """
    Run LAMMPS for some number of iterations
    """
    templated = create_lammps_template(pods)

    metrics_yaml = os.path.join(data_path, f"lammps-{pods}.yaml")
    write_file(templated, metrics_yaml)

    # Make a cache directory assuming I'm going to screw something up
    cache_dir = os.path.join(data_path, "cache", str(pods))
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)

    # Cheat and update the kubeconfig-aws.yaml
    kubeconfig = os.path.join(here, "kubeconfig-aws.yaml")
    m = MetricsOperator(metrics_yaml, kubeconfig=kubeconfig)
    m.create()
    time.sleep(sleep)

    # Save listing of run results
    runs = []
    name = m.spec["metadata"]["name"]
    pod_prefix = f"{name}-l-0"
    worker_prefix = f"{name}-w-"

    # Was it terminated?
    terminated = False

    # Now run lammps some number of times.
    for i in range(0, iters):
        print(f"🪔️ Running iteration {i} of LAMMPS")
        m.create()
        if i == 0:
            print(templated)
            print(f"Sleeping {sleep} seconds so container can pull...")
            time.sleep(sleep)
        else:
            time.sleep(5)
        cache_file = os.path.join(cache_dir, f"lammps-{i}.json")
        output, terminated = get_lammps_output(m, pod_prefix, cache_file)
        runs.append(output)
        if terminated:
            print(f"😭️ Lammps run {i} was terminated, ending iterations early.")
            break

        # Wait for leader to terminate
        m.delete(pod_prefix)

        # Wait for workers to terminate too
        m.wait_for_delete(worker_prefix)
    return runs


def get_lammps_output(m, pod_prefix, cache_file):
    """
    Get lammps output, preparing for an error

    In the case of an error, we cannot parse the logs and fall
    back to raw output.
    """
    # Try for parsed output
    try:
        for output in m.watch():
            print(json.dumps(output, indent=4))

            # Save single result file to cache to be conservative
            write_json(output, cache_file)
            return output, False

    # Fall back to raw logs
    except:
        for output in m.watch(
            raw_logs=True, pod_prefix=pod_prefix, container_name="launcher"
        ):
            write_json(output, cache_file)
            return output, True


def save_nodes(outfile):
    """
    Cheap way to save nodes
    """
    print(f"🥸️ Saving nodes to {outfile}")
    os.system(
        f"KUBECONFIG={here}/kubeconfig-aws.yaml kubectl get nodes -o json > {outfile}"
    )


def install_operators():
    """
    Install jobset followed by the metrics operator
    """
    print("📊️ Installing JobSet and Metrics Operator")
    # This installs JobSet
    os.system(
        f"KUBECONFIG={here}/kubeconfig-aws.yaml kubectl apply --server-side -f https://github.com/kubernetes-sigs/jobset/releases/download/v0.2.0/manifests.yaml"
    )

    time.sleep(10)
    # And the metrics operator
    os.system(
        f"KUBECONFIG={here}/kubeconfig-aws.yaml kubectl apply -f https://raw.githubusercontent.com/converged-computing/metrics-operator/main/examples/dist/metrics-operator.yaml"
    )


def run_spot_experiments(args, count, data_dir):
    """
    Wrap experiment running separately in case we lose spot nodes and can recover
    """
    # Be lazy and use the kubeconfig that is local!
    # I am a terrible person... should do this programatically...
    install_operators()

    # Generate the template for the size
    lammps_results = run_lammps(args.nodes, args.iters, data_dir, sleep=args.sleep)
    outfile = os.path.join(
        data_dir, f"lammps-nodes-{args.nodes}-request-count-{count}.json"
    )
    write_json(lammps_results, outfile)

    # Get hwloc files for unique node types
    unique_machines = run_hwloc(args.nodes, data_dir, sleep=args.sleep)
    outfile = os.path.join(data_dir, f"hwloc-unique-machines-nodes-{args.nodes}.json")
    write_json(unique_machines, outfile)


def main():
    """
    Demonstrate creating and deleting a cluster. If the cluster exists,
    we should be able to retrieve it and not create a second one.
    """
    parser = get_parser()

    # If an error occurs while parsing the arguments, the interpreter will exit with value 2
    args, _ = parser.parse_known_args()

    if not args.plan or not os.path.exists(args.plan):
        sys.exit("A --plan is required to run for an experiment.")

    if not os.path.exists(args.data_dir):
        os.makedirs(args.data_dir)

    # Min cannot be >= max
    if args.min_spot_request >= args.max_spot_request:
        sys.exit("Oops, the minimum spot request needs to be less than the max!")

    # plan experiments!
    experiments = plan_experiments(args)
    count = len(range(args.min_spot_request, args.max_spot_request))
    print("🧪️ Experiments:")
    for exp in experiments:
        print(f"   {exp}")

    print("🪴️ Planning to run:")
    print(f"   Cluster name        : {args.cluster_name}")
    print(f"   Output Data         : {args.data_dir}")
    print(f"   Experiments         : {len(experiments)}")
    print(f"   Nodes requested     : {args.nodes}")
    print(f"   Max Instance Types  : {args.max_instance_types}")
    print(
        f"   Range Spot Requests : {count} ({args.min_spot_request} to {args.max_spot_request})"
    )
    if not confirm_action("Would you like to continue?"):
        sys.exit("Cancelled!")

    # Use kubescaler ekscluster to create the cluster
    # We will request / delete nodegroups from it
    cli = EKSCluster(
        name=args.cluster_name,
        eks_nodegroup=True,
        capacity_type="SPOT",
        node_count=args.nodes,
        min_nodes=args.nodes,
        max_nodes=args.nodes,
    )

    # Note we are NOT creating the node group here - just the cluster, so machine types aren't relevant
    # We will add machine types as node groups (to create and delete from the cluster) later
    cli.create_cluster(create_nodes=False)

    # Save results as we go!
    original_times = cli.times
    results = {
        "experiments": {},
        "times": original_times,
        "nodes": args.nodes,
        "cluster_name": args.cluster_name,
    }

    for name, exp in experiments.items():
        print(f"== Experiment {exp.id} has {exp.count} instances selected.")

        # Add specific experiment to results
        results["experiments"][name] = exp.export()

        # Data directory for the experiment
        data_dir = os.path.join(args.data_dir, exp.id)
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)

        # Final output file therein
        final_outfile = os.path.join(data_dir, f"{args.cluster_name}-results.json")

        # We will generate from args.min (2) up to the count
        for count in range(args.min_spot_request, args.max_spot_request):
            # Reset times between experiments
            cli.times = {}

            # Here we select our random machine types from the set (this shows/prints it too)
            # This returns a subset of the data frame. The entire experiment df is saved with experiment
            subset = exp.select_machine_types(count)
            machine_types = list(subset.instance.values)

            # Now create the node groups!
            cli.create_cluster_nodes(machine_types)
            outfile = os.path.join(
                data_dir, f"nodes-{args.nodes}-request-count-{count}.json"
            )
            save_nodes(outfile)

            # Wrap this entire thing in case we lose our spot instances
            # Wrap the total time (this might reflect how long to lose spot)
            try:
                start_experiments = time.time()
                run_spot_experiments(args, count, data_dir)
            except:
                print("😿️ Oh no, there was an error! Did we lose our spot?")
            stop_experiments = time.time()

            # And now... delete it! We don't need it, lol
            cli.delete_nodegroup(cli.node_group_name)

            # Add cluster times to the new times
            times = copy.deepcopy(original_times)
            times.update(cli.times)
            times["experiments_seconds"] = stop_experiments - start_experiments

            # Save metadata as we go - the times include for the cluster too
            # We might as well make mean price easy to see too
            new_result = {
                "machine_types": machine_types,
                "nodes": args.nodes,
                "count": count,
                "times": times,
                "mean_price": subset.price.mean(),
                "std_price": subset.price.std(),
            }
            print(json.dumps(new_result))
            results["experiments"][name]["runs"].append(new_result)
            write_json(results, final_outfile)

    # When we are done, delete the cluster
    cli.times = {}
    cli.delete_cluster()

    # Update original times with deletion times
    times = copy.deepcopy(original_times)
    times.update(cli.times)
    results["times"] = times
    write_json(results, final_outfile)


if __name__ == "__main__":
    main()
