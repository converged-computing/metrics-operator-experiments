#!/usr/bin/env python3

import random
import argparse
import os
import sys
import subprocess

here = os.path.abspath(os.path.dirname(__file__))
collect_script = os.path.join(here, "collect.sh")
metrics_yaml = os.path.join(here, "crd", "metrics-16-subset.yaml")


def get_parser():
    parser = argparse.ArgumentParser(
        description="Run OSU Benchmarks Randomly",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "-p",
        help="run at a particular probability",
        type=float,
    )
    parser.add_argument(
        "--force",
        help="force a run",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "--project",
        help="Google project",
    )
    parser.add_argument(
        "-c", help="cluster to run (defaults to 3)", type=int, default=3
    )
    return parser


def main():
    """
    Run multiple OSU benchmark jobs, based on size.

    Experiment design is represented in the yaml input files.
    """
    parser = get_parser()
    args, _ = parser.parse_known_args()

    if not args.p and not args.force:
        sys.exit(
            "Please set -p to indicate a float (between 0 and 100) that indicates a probability of running"
        )
    if not args.project:
        sys.exit("--project is required.")

    import IPython

    IPython.embed()
    sys.exit()
    dorun = random.choice(range(0, 100)) < args.p or args.force
    if not dorun:
        sys.exit("We are not running this time!")

    # This will create the cluster, run the operator, and clean up
    for i in range(0, args.c):
        print(f"🥞️ Running top level iteration {i}")
        res = subprocess.run(["bash", collect_script, args.project, "18", metrics_yaml])


if __name__ == "__main__":
    main()
