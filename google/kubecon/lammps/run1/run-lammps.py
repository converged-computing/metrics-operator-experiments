#!/usr/bin/env python3

import argparse
import os
import json
import time
from metricsoperator import MetricsOperator
import metricsoperator.utils as utils

here = os.path.abspath(os.path.dirname(__file__))

def get_parser():
    parser = argparse.ArgumentParser(
        description="Run LAMMPS and Get Output",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--out", help="directory to save results", default=os.path.join(here, "data")
    )
    parser.add_argument(
        "--sleep",
        help="seconds to sleep allowing for pull and run",
        type=int,
        default=60,
    )
    parser.add_argument(
        "--iter",
        help="number of iterations to run",
        type=int,
        default=5,
    )
    parser.add_argument(
        "--input",
        help="input file to run",
    )
    return parser


def main():
    """
    Run multiple lammps jobs, based on size.

    This script does not expect interactive: true to be set, it's automated.
    We have to run it on the level of the individual script because some job
    sizes (e.g., 16) will just not run. I might run the hpctoolkit benchmark
    first to pull containers (a more manual apply and save) so that I know
    which ones to automate after based on times.
    """
    parser = get_parser()
    args, _ = parser.parse_known_args()
    result_dir = args.out

    # The output file is based on the input file name
    indir = os.path.relpath(args.input, here)
    outname = indir.split(".")[0].replace(os.sep, "-")
    outfile = os.path.join(os.path.abspath(result_dir), f"{outname}.json")
    cache_dir = os.path.join(os.path.abspath(result_dir), "cache")
    metrics_yaml = os.path.abspath(args.input)

    for dirname in [cache_dir, result_dir]:
        if not os.path.exists(dirname):
            os.makedirs(dirname)

    # Save listing of results (as we go)
    results = []

    # Create a metrics operator with our metrics.yaml
    m = MetricsOperator(metrics_yaml)
    pod_prefix = f"{m.name}-l-0"
    worker_prefix = f"{m.name}-w-0"
    for i in range(args.iter):
        print(f"Running LAMMPS iteration {i}")
        m.create()

        # Sleep to allow pull on first iteration
        if i == 0:
            print(f"Sleeping {args.sleep} seconds so container can pull...")
            time.sleep(args.sleep)
        else:
            time.sleep(5)

        # Raw logs ensures we don't do custom parsing here (and get the full log)
        for output in m.watch(
            raw_logs=True, pod_prefix=pod_prefix, container_name="launcher"
        ):
            print(json.dumps(output, indent=4))

            # Save single result file to cache to be conservative
            cache_file = os.path.join(cache_dir, f"{outname}-{i}.json")
            cache_result = {"data": output, "spec": m.spec}
            utils.write_json(cache_result, cache_file)

            # Append final results
            results.append(output)

        # Wait for leader to terminate
        m.delete(pod_prefix)

        # Wait for workers to terminate too
        m.wait_for_delete(worker_prefix)

    utils.write_json(results, outfile)


if __name__ == "__main__":
    main()
