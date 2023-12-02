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
import metricsoperator.utils as utils

here = os.path.dirname(os.path.abspath(__file__))
templates = os.path.join(here, "metrics")

lammps_template = utils.read_file(os.path.join(templates, "mpitrace-lammps.yaml"))
hwloc_template = utils.read_file(os.path.join(templates, "hwloc.yaml"))
hpctoolkit_template = utils.read_file(os.path.join(templates, "hpctoolkit.yaml"))

# This is hard coded for a small kubectl cluster size (local with kind)
# And assumes the cluster is running with the metrics and oras operators installed.

def get_parser():
    parser = argparse.ArgumentParser(
        description="Performance Experiment Running",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--iters",
        help="iterations of lammps to run",
        type=int,
        default=10,
    )
    parser.add_argument(
        "--data-dir",
        help="path to save data",
        default=os.path.join(here, "data"),
    )
    parser.add_argument(
        "--sleep",
        help="Sleep time for first LAMMPS run (to pull)",
        type=int,
        default=60,
    )
    return parser


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


def create_template(tag, template):
    """
    Generate the lammps templated yaml, filling in size and number of processes
    """
    replaces = {"[[TAG]]": tag}
    templated = template
    for k, v in replaces.items():
        templated = templated.replace(k, v)
    return templated


def run_hwloc(tag, data_path, sleep=60):
    """
    Run hwloc
    """
    templated = create_template(tag, hwloc_template)
    metrics_yaml = os.path.join(data_path, f"hwloc-{tag}.yaml")
    write_file(templated, metrics_yaml)

    # Get a handle to the metrics operator
    m = MetricsOperator(metrics_yaml)
    m.create()
    time.sleep(sleep)

    # We don't have an hwloc parser, so we mostly need to wait for them to be running
    parser = m.get_parser(container_name="app")

    # Get nodes (to see unique). Let's compare what the kubelet sees to hwloc
    unique_machines = {}
    production_cluster = True
    for node in parser.core_v1.list_node().items:
        if "node.kubernetes.io/instance-type" not in node.metadata.labels:
            print("Warning: we are not running on a production cluster.")
            production_cluster = False
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

    # If we have a production cluster, get hwloc data for each node type
    node_names = None
    if production_cluster:
        print(f"🤡️ This cluster has {len(unique_machines)} unique node type(s).")

        # These are the nodes we need to find assignments to
        node_names = {x["name"]: mt for mt, x in unique_machines.items()}

    # Wait for all pods to be running
    # TODO this will save one artifact for one node, and given more than one type
    # we need to be able to support that. Probably OK for now.
    print("🕰️  Waiting for hwloc pods to be finished...")
    pod_prefix = m.spec["metadata"]["name"]
    parser.wait(pod_prefix=pod_prefix, states=["Succeeded"])
    time.sleep(sleep)
    m.delete(pod_prefix=m.spec["metadata"]["name"])
    return unique_machines


def run_lammps(iters, data_path, sleep=60):
    """
    Run LAMMPS for some number of iterations
    """
    # Now run lammps some number of times.
    for i in range(0, iters):
        print(f"🪔️ Running iteration {i} of LAMMPS")
        tag = f"iter-{i}"
        templated = create_template(tag, lammps_template)
        metrics_yaml = os.path.join(data_path, f"lammps-{tag}.yaml")
        write_file(templated, metrics_yaml)

        # Cheat and update the kubeconfig-aws.yaml
        m = MetricsOperator(metrics_yaml)
        name = m.spec["metadata"]["name"]
        pod_prefix = f"{name}-l-0"
        worker_prefix = f"{name}-w-"
        m.create()
        if i == 0:
            print(templated)

        # Wait for leader to finish - mpitrace uses an initContainer
        time.sleep(sleep)
        for output in m.watch(pod_prefix=pod_prefix, container_name="launcher"):
            print(output)

        # Wait until succeeded
        parser = m.get_parser()
        parser.wait(states=["Succeeded"], pod_prefix=pod_prefix)
        m.delete(pod_prefix)

        # Wait for workers to terminate too
        m.wait_for_delete(worker_prefix)


def run_hpctoolkit(iters, data_path, sleep=60):
    """
    Run hpctoolkit
    """
    # Now run lammps some number of times.
    for i in range(0, iters):
        print(f"🪔️ Running iteration {i} of HPCToolkit")
        tag = f"iter-{i}"
        templated = create_template(tag, hpctoolkit_template)
        metrics_yaml = os.path.join(data_path, f"hpctoolkit-{tag}.yaml")
        write_file(templated, metrics_yaml)

        # Cheat and update the kubeconfig-aws.yaml
        m = MetricsOperator(metrics_yaml)
        name = m.spec["metadata"]["name"]
        pod_prefix = f"{name}-l-0"
        m.create()
        if i == 0:
            print(templated)

        # Wait for leader to finish - mpitrace uses an initContainer
        time.sleep(sleep)
        for output in m.watch(pod_prefix=pod_prefix, container_name="launcher"):
            print(output)

        # Wait until succeeded
        parser = m.get_parser()
        parser.wait(states=["Succeeded"], pod_prefix=pod_prefix)
        m.delete(pod_prefix)


def run_experiments(args, data_dir):
    """
    Wrap experiment running separately in case we lose spot nodes and can recover
    """
    # Run lammps - results are saved to the OCI registry
    run_hpctoolkit(args.iters, data_dir, sleep=args.sleep)
    run_lammps(args.iters, data_dir, sleep=args.sleep)

    # Get hwloc files for one node type (TODO - need to be able to run for each node type)
    # This call assumes the nodes are the same
    unique_machines = run_hwloc("iter-0", data_dir, sleep=args.sleep)
    outfile = os.path.join(data_dir, f"hwloc-unique-machines-nodes.json")
    write_json(unique_machines, outfile)
    print("Experiments are done! Next, use ingress.yaml to pull ORAS artifacts.")


def main():
    """
    Demonstrate creating and deleting a cluster. If the cluster exists,
    we should be able to retrieve it and not create a second one.
    """
    parser = get_parser()

    # If an error occurs while parsing the arguments, the interpreter will exit with value 2
    args, _ = parser.parse_known_args()

    if not os.path.exists(args.data_dir):
        os.makedirs(args.data_dir)

    print("🪴️ Planning to run:")
    print(f"   Experiments         : LAMMPS + HWLOC")
    print(f"   Output Data         : {args.data_dir}")

    start_experiments = time.time()
    run_experiments(args, args.data_dir)
    stop_experiments = time.time()
    total = stop_experiments - start_experiments
    print(f"total time to run is {total} seconds")


if __name__ == "__main__":
    main()
