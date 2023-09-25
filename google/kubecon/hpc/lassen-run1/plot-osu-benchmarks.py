import argparse
import fnmatch
import json
import os
import re

import matplotlib.pyplot as plt
import pandas
import seaborn as sns
from metricsoperator import utils as utils
from metricsoperator.metrics import get_metric
from metricsoperator.metrics.network.osu_benchmark import run_parsing_function

plt.style.use("bmh")
here = os.path.dirname(os.path.abspath(__file__))

# Separator for runs within a size file
separator = "=============="


def get_parser():
    parser = argparse.ArgumentParser(
        description="Plot OSU Benchmarks",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--results",
        help="directory with raw results data",
        default=os.path.join(here, "data", "osu-benchmarks"),
    )
    parser.add_argument(
        "--out",
        help="directory to save parsed results",
        default=os.path.join(here, "img", "osu-benchmarks"),
    )
    return parser


def recursive_find(base, pattern="*.*"):
    """
    Recursively find and yield files matching a glob pattern.
    """
    for root, _, filenames in os.walk(base):
        for filename in fnmatch.filter(filenames, pattern):
            yield os.path.join(root, filename)


def find_inputs(input_dir):
    """
    Find json inputs (results files)
    """
    files = []
    for filename in recursive_find(input_dir, pattern="*.out"):
        files.append(filename)
    return files


def main():
    """
    Run the main plotting operation!
    """
    parser = get_parser()
    args, _ = parser.parse_known_args()

    # Output images and data
    outdir = os.path.abspath(args.out)
    indir = os.path.abspath(args.results)
    if not os.path.exists(outdir):
        os.makedirs(outdir)

    # Find input files (skip anything with test)
    files = find_inputs(indir)
    if not files:
        raise ValueError(f"There are no input files in {indir}")

    # This does the actual parsing of data into a formatted variant
    # Has keys results, iters, and columns
    results = parse_data(files)
    utils.write_json(results, os.path.join(outdir, "lassen-results.json"))
    # Save raw results (and data frames for each)
    # save_data(results, outdir)
    # plot_results(results, outdir)


def save_data(results, outdir):
    """
    Save all data in results to output directory.
    """
    utils.write_json(results["iters"], os.path.join(outdir, "iterations.json"))
    utils.write_json(results["columns"], os.path.join(outdir, "columns.json"))

    # Full dataframes with results
    for name, df in results["results"].items():
        df.to_csv(os.path.join(outdir, f"{name}-2-to-16.csv"))
        try:
            # Show (and save) grouped by data) (skip those without numberic like osu_hello)
            if "Size" in df.columns:
                group = df.groupby(["pods", "Size"]).mean()
            else:
                group = df.groupby("pods").mean()
            print(group)
            group.to_csv(os.path.join(outdir, f"{name}-groups-2-to-16.csv"))
        except:
            print(f"Skipping {name}, likely not numeric data.")

    # Times to do the runs (wrappers)
    if "times" not in results:
        return

    for name, df in results["times"].items():
        df.to_csv(os.path.join(outdir, f"{name}-time-wrapper-seconds-2-to-16.csv"))

        # Show (and save) grouped by data)
        group = df.groupby("pods").mean()
        print(group)
        group.to_csv(
            os.path.join(outdir, f"{name}-time-wrapper-seconds-groups-2-to-16.csv")
        )


def parse_data(files):
    """
    Given a listing of files, parse into results data frame
    """
    # Derive metric handle (empty without a spec)
    m = get_metric("network-osu-benchmark")()

    # Read in output files and organize data frames by nodes, then identifier, then list of raw data
    results = {}

    for filename in files:
        content = utils.read_file(filename)
        sections = content.split(separator)

        # The first "section" indicates the number of nodes
        nodes = sections.pop(0)
        nodes = int((nodes.strip().split(":")[-1]).strip())
        if nodes not in results:
            results[nodes] = {}

        for section in sections:
            lines = section.split("\n")

            # Get rid of the header
            lines = lines[3:]

            # Separated by the time jsrun line
            result = {"data": []}
            identifier = None

            for line in lines:
                # This is the start of a block
                if "time jsrun" in line:
                    # Save the previous result
                    if result and identifier:
                        if identifier not in results[nodes]:
                            results[nodes][identifier] = []
                        results[nodes][identifier].append(result)
                    identifier = line.split("/")[-1]
                    result = {"data": [], "command": line, "identifier": identifier}
                    continue
                else:
                    result["data"].append(line)

    # Now for each, artificially assemble into metrics operator result to parse
    # TODO this needs further parsing into data frames
    # I don't have the spirit to take this on today.
    # for nodes, result in results.items():
    #    for metric, r in result.items():
    #        for section in r:
    #            datum = run_parsing_function(section['command'] + "\n" + "\n".join(section['data']))
    #        results.append(datum)
    #
    return results


if __name__ == "__main__":
    main()
