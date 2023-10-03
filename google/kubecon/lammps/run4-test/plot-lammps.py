#!/usr/bin/env python3

import argparse
import collections
import fnmatch
import os

import matplotlib.pyplot as plt
import metricsoperator.utils as utils
import pandas
import seaborn as sns
from metricsoperator.metrics import get_metric

plt.style.use("bmh")
here = os.path.dirname(os.path.abspath(__file__))


def get_parser():
    parser = argparse.ArgumentParser(
        description="Plot LAMMPS",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--results",
        help="directory with raw results data",
        default=os.path.join(here, "data", "lammps"),
    )
    parser.add_argument(
        "--out",
        help="directory to save parsed results",
        default=os.path.join(here, "img", "lammps"),
    )
    return parser


def recursive_find(base, pattern="*.*"):
    """
    Recursively find and yield files matching a glob pattern.
    """
    for root, _, filenames in os.walk(base):
        for filename in fnmatch.filter(filenames, pattern):
            yield os.path.join(root, filename)


def find_json_inputs(input_dir):
    """
    Find json inputs (results files)
    """
    files = []
    for filename in recursive_find(input_dir, pattern="*.json"):
        # We only have data for small
        if "-small-" not in filename or "cache" in filename:
            continue
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
    files = find_json_inputs(indir)
    if not files:
        raise ValueError(f"There are no input files in {indir}")

    # This does the actual parsing of data into a formatted variant
    # Has keys results, iters, and columns
    df = parse_data(files)
    df.to_csv(os.path.join(outdir, "lammps-times.csv"))
    plot_results(df, outdir)


def plot_results(df, outdir):
    """
    Plot lammps results
    """
    # Plot each!
    colors = sns.color_palette("hls", 16)
    hexcolors = colors.as_hex()
    types = list(df.ranks.unique())

    # ALWAYS double check this ordering, this
    # is almost always wrong and the colors are messed up
    palette = collections.OrderedDict()
    for t in types:
        palette[t] = hexcolors.pop(0)

    make_plot(
        df,
        title="LAMMPS Times (2x2x2)",
        tag="lammps",
        ydimension="time",
        xdimension="ranks",
        palette=palette,
        outdir=outdir,
        ext="png",
        plotname="lammps",
        hue="ranks",
        plot_type="bar",
        xlabel="MPI Ranks",
        ylabel="Time (seconds)",
    )

    colors = sns.color_palette("hls", 16)
    hexcolors = colors.as_hex()
    types = list(df.pods.unique())

    # ALWAYS double check this ordering, this
    # is almost always wrong and the colors are messed up
    palette = collections.OrderedDict()
    for t in types:
        palette[t] = hexcolors.pop(0)

    make_plot(
        df,
        title="LAMMPS Times (2x2x2) by Nodes (56 ranks each)",
        tag="lammps-pods",
        ydimension="time",
        xdimension="pods",
        palette=palette,
        outdir=outdir,
        ext="png",
        plotname="lammps-nodes",
        hue="pods",
        plot_type="bar",
        xlabel="Nodes",
        ylabel="Time (seconds)",
    )


def parse_data(files):
    """
    Given a listing of files, parse into results data frame
    """
    # Parse into data frame
    df = pandas.DataFrame(columns=["ranks", "pods", "time"])
    idx = 0
    m = get_metric("app-lammps")()

    for filename in files:
        # This is a list, each a json result, 20x
        items = utils.read_json(filename)
        for item in items:
            # Parse the data into a result, including times
            # The parser expects a raw log (not by lines)
            data = "\n".join(item["data"])

            result = m.parse_log(data)

            # These are used for identifiers across the data
            pods = result["metadata"]["pods"]
            for datum in result["data"]:
                loop_time = datum["loop_time"]
                ranks = datum["ranks"]
                df.loc[idx, :] = [ranks, pods, loop_time]
                idx += 1
    return df


def make_plot(
    df,
    title,
    tag,
    ydimension,
    xdimension,
    palette,
    xlabel,
    ylabel,
    ext="pdf",
    plotname="lammps",
    plot_type="violin",
    hue="ranks",
    outdir="img",
):
    """
    Helper function to make common plots.
    """
    plotfunc = sns.boxplot
    if plot_type == "violin":
        plotfunc = sns.violinplot

    ext = ext.strip(".")
    plt.figure(figsize=(20, 12))
    sns.set_style("dark")
    ax = plotfunc(
        x=xdimension, y=ydimension, hue=hue, data=df, whis=[5, 95], palette=palette
    )
    plt.title(title)
    ax.set_xlabel(xlabel, fontsize=16)
    ax.set_ylabel(ylabel, fontsize=16)
    ax.set_xticklabels(ax.get_xmajorticklabels(), fontsize=14)
    ax.set_yticklabels(ax.get_yticks(), fontsize=14)
    plt.savefig(os.path.join(outdir, f"{tag}_{plotname}.{ext}"))
    plt.clf()


if __name__ == "__main__":
    main()
