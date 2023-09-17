#!/usr/bin/env python3

import argparse
import os
import json
import time

from metricsoperator import MetricsOperator
import metricsoperator.utils as utils

here = os.path.abspath(os.path.dirname(__file__))


# Matrix of sizes and block sizes to write
sizes = ["4G", "3G", "2G", "1G"]
blocksizes = ["8k", "32k", "64k", "128k", "256k"]


def get_parser():
    parser = argparse.ArgumentParser(
        description="Run Fio Metric and Get Output",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--out",
        help="json prefix to save results.",
        default=os.path.join(here, "metrics.json"),
    )
    parser.add_argument(
        "filename",
        help="yaml in present working directory to apply",
        default="metrics-filestore.yaml",
    )
    parser.add_argument(
        "--sleep",
        help="seconds to sleep (for container to pull)",
        default=60,
        type=int,
    )
    return parser


def main():
    parser = get_parser()
    args, _ = parser.parse_known_args()
    yaml_template = os.path.join(here, args.filename)
    template = utils.read_file(yaml_template)
    outdir = os.path.dirname(args.out)
    i = 0

    for size in sizes:
        for blocksize in blocksizes:
            # Output json based on prefix
            outfile = f"{args.out}-{size}-{blocksize}.json"

            # Don't run again if we have it!
            if os.path.exists(outfile):
                continue

            print(f"Testing size {size} and blocksize {blocksize}")
            tmp = template.replace("SUB_SIZE", size).replace("SUB_BLOCKSIZE", blocksize)
            print(tmp)
            metrics_yaml = os.path.join(
                outdir, f"metrics-filestore-{size}-{blocksize}.yaml"
            )
            utils.write_file(tmp, metrics_yaml)

            # Create a metrics operator with our metrics.yaml
            m = MetricsOperator(metrics_yaml)
            m.create()

            # Give pods time to create
            if i == 0:
                print("Sleeping to give containers time to pull...")
                time.sleep(args.sleep)
            else:
                time.sleep(5)
            for output in m.watch():
                print(json.dumps(output, indent=4))
                utils.write_json(output, outfile)
            print("Clean up")
            m.delete()
            i += 1


if __name__ == "__main__":
    main()
