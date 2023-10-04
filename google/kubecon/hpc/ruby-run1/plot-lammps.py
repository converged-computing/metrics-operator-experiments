#!/usr/bin/env python3

import argparse
import collections
import fnmatch
import os

import matplotlib.pyplot as plt
import metricsoperator.utils as utils
import pandas
import seaborn as sns
from metricsoperator.metrics.app.lammps import parse_lammps

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
        default=os.path.join(here, "data"),
    )
    parser.add_argument(
        "--out",
        help="directory to save parsed results",
        default=os.path.join(here, "img"),
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
    Find inputs (results files)
    """
    files = []
    for filename in recursive_find(input_dir, pattern="*.out"):
        # We only have data for small
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
    df, times = parse_data(files)
    df.to_csv(os.path.join(outdir, "lammps-times.csv"))
    times.to_csv(os.path.join(outdir, "lammps-times-by-call-type.csv"))
    plot_results(df, times, outdir)


def plot_results(df, times_df, outdir):
    """
    Plot lammps results
    """
    # Plot each!
    colors = sns.color_palette("hls", 16)
    hexcolors = colors.as_hex()
    types = list(df.ranks.unique())
    types.sort()

    # ALWAYS double check this ordering, this
    # is almost always wrong and the colors are messed up
    palette = collections.OrderedDict()
    for t in types:
        palette[t] = hexcolors.pop(0)

    make_plot(
        df,
        title="LAMMPS Times (64x16x16)",
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

    # Plot each of the times we care about, point to point and comm
    make_plot(
        times_df,
        title="LAMMPS Times (64x16x16) Percent Total Time Spent in MPI Communication Type",
        tag="lammps-communication-type",
        ydimension="percent_time",
        xdimension="call_type",
        palette=palette,
        outdir=outdir,
        ext="png",
        plotname="lammps-times-mpi-communication-type",
        hue="ranks",
        plot_type="bar",
        xlabel="MP Ranks",
        ylabel="Percentage Total Time",
    )


def parse_data(files):
    """
    Given a listing of files, parse into results data frame
    """
    # Parse into data frame
    df = pandas.DataFrame(columns=["ranks", "time"])
    times_df = pandas.DataFrame(
        columns=[
            "ranks",
            "percent_time",
            "call_type",
        ]
    )
    idx = 0
    idx_times = 0

    for filename in files:
        pieces = os.path.basename(filename).split("_")
        ranks = int(pieces[2])
        iter = int(pieces[3])

        # This is a list, each a json result, 20x
        item = utils.read_file(filename)

        # Full command is the first item
        lines = [x for x in item.split("\n") if x]
        command = lines.pop(0)
        item = "\n".join(lines)
        result = parse_lammps(item)

        # These are used for identifiers across the data
        loop_time = result["loop_time"]
        ranks = result["ranks"]
        df.loc[idx, :] = [ranks, loop_time]
        idx += 1

        for call_row in result["times"]["matrix"]:
            call_type = call_row[0]
            call_time = call_row[-1]
            times_df.loc[idx_times, :] = [ranks, call_time, call_type]
            idx_times += 1

    return df, times_df


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
