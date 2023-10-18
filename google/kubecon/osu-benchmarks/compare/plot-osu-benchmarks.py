import argparse
import fnmatch
import os
import re
import sys

import matplotlib.pyplot as plt
import pandas
import seaborn as sns
from metricsoperator import utils as utils

plt.style.use("bmh")
here = os.path.dirname(os.path.abspath(__file__))


def get_parser():
    parser = argparse.ArgumentParser(
        description="Plot OSU Benchmarks",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--out",
        help="directory to save parsed results",
        default=os.path.join(here, "img"),
    )
    return parser


def read_gcp_data(filename, environment):
    df = pandas.read_csv(os.path.join(here, filename), index_col=0)
    df = df.rename(columns={"pods": "nodes"})
    df = df.drop("iter", axis=1)
    df["environment"] = environment
    return df


def main():
    """
    Run the main plotting operation!
    """
    parser = get_parser()
    args, _ = parser.parse_known_args()

    # Output images and data
    outdir = os.path.abspath(args.out)
    if not os.path.exists(outdir):
        os.makedirs(outdir)

    # We have time to show one point to point (latency) and one collective
    df_reduce = pandas.read_csv(
        os.path.join(here, "osu_allreduce-2-to-128.csv"), index_col=0
    )
    df_reduce["environment"] = "hpc"

    # The other df uses nodes instead of pods, and does not have an iter column
    # Note that we have fewer data points because it took much longer to run here
    df_reduce_gcp = read_gcp_data("osu_allreduce-4-to-128-gcp.csv", "cloud")

    # Add label for cloud or hpc to size
    nodes = list(df_reduce["nodes"])
    labels = []
    for size in nodes:
        labels.append(f"hpc-{size}")
    df_reduce["label"] = labels

    nodes = list(df_reduce_gcp["nodes"])
    labels = []
    for size in nodes:
        labels.append(f"cloud-{size}")
    df_reduce_gcp["label"] = labels

    # Combine them!
    df_reduce_comb = pandas.concat([df_reduce, df_reduce_gcp])
    df_reduce_comb.to_csv(os.path.join(here, "osu_allreduce-combined.csv"))

    print(f"Plotting boxplot for allreduce")
    plot_pairs(
        df_reduce,
        hue="nodes",
        x="Size",
        y="Avg Latency(us)",
        slug="allreduce-hpc",
        outdir=outdir,
        title="All Reduce Average Latency High Performance Computing System (microseconds) across node sizes",
    )
    plot_pairs(
        df_reduce_gcp,
        hue="nodes",
        x="Size",
        y="Avg Latency(us)",
        slug="allreduce-cloud-c2d",
        outdir=outdir,
        title="All Reduce Average Latency Cloud (microseconds) across node sizes",
    )
    plot_pairs(
        df_reduce_comb,
        hue="label",
        x="Size",
        y="Avg Latency(us)",
        slug="allreduce-cloud-vs-hpc",
        outdir=outdir,
        title="All Reduce Average Latency Cloud vs HPC (microseconds) across node sizes",
    )

    # Try to compare just size 64 for allreduce - too much data
    df_reduce_64 = df_reduce_comb[df_reduce_comb.nodes == 64]
    plot_pairs(
        df_reduce_64,
        hue="environment",
        x="Size",
        y="Avg Latency(us)",
        slug="allreduce-cloud-vs-hpc-size-64",
        outdir=outdir,
        title="All Reduce Average Latency Cloud vs HPC (microseconds) 64 Nodes",
    )

    # Compare latency
    df_latency = pandas.read_csv(
        os.path.join(here, "osu_latency-2-to-128.csv"), index_col=0
    )
    df_latency["environment"] = "hpc"

    # The other df uses nodes instead of pods, and does not have an iter column
    # Note that we have fewer data points because it took much longer to run here
    df_latency_gcp = read_gcp_data("osu_latency-4-to-128-gcp.csv", "cloud")

    # Ensure they are both the same data type, ug, pandas why
    # df_latency.Size =  pandas.to_numeric(df_latency.Size, downcast='integer')
    # df_latency_gcp.Size = pandas.to_numeric(df_latency_gcp.Size, downcast='integer')
    df_latency_comb = pandas.concat([df_latency, df_latency_gcp])
    df_latency_comb.to_csv(os.path.join(here, "osu_latency-combined.csv"))
    groups = df_latency_comb.groupby(["Size", "environment"]).mean()
    groups.to_csv(os.path.join(here, "osu_latency-groups-combined.csv"))

    # Finally, consolidate across the sizes (they don't really matter)
    plot_pairs(
        df_latency_comb,
        hue="environment",
        x="Size",
        y="Latency(us)",
        dodge=False,
        width=0.5,
        slug="latency-by-cloud",
        outdir=outdir,
        title="Average Point to Point Latency High Performance Computing System vs. Cloud (microseconds) across node sizes",
    )


def plot_pairs(
    df,
    slug,
    x,
    y,
    title,
    outdir,
    logarithmic=True,
    hue="nodes",
    dodge=True,
    width=None,
    fig_width=28,
    fig_height=10,
):
    """
    Plot two values, and and y, over time.

    We always plot these with larger size
    """
    # For bandwith, higher is better
    memo = "higher is better"
    if "latency" in y.lower():
        memo = "lower is better"
    xlabel = "Packet size (bits)"

    # Prepare y label, optionally with logarithmic
    ylabel = y + " " + memo
    if logarithmic:
        ylabel = y + " " + memo + " (logscale)"

    # Make x int, never actually a float
    df[x] = [int(x) for x in df[x]]
    if width is not None:
        ax2 = sns.boxplot(
            data=df, x=x, y=y, hue=hue, palette="muted", dodge=dodge, width=width
        )
    else:
        ax2 = sns.boxplot(data=df, x=x, y=y, hue=hue, palette="muted", dodge=dodge)
    outfile = os.path.join(outdir, f"{slug}-box-2-to-128.png")
    make_plot(
        ax2,
        slug=slug,
        title=title,
        outfile=outfile,
        xlabel=xlabel,
        ylabel=ylabel,
        logarithmic=logarithmic,
        fig_width=fig_width,
        fig_height=fig_height,
    )


def make_plot(
    ax,
    slug,
    title,
    outfile,
    xlabel=None,
    ylabel=None,
    larger_size=True,
    logarithmic=True,
    fig_width=28,
    fig_height=10,
):
    """
    Generic plot making function for some x and y
    """
    # for sty in plt.style.available:
    sns.set(rc={"figure.figsize": (fig_width, fig_height)})
    plt.title(title)

    # For bandwith, higher is better
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=16)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=16)
    ax.set_xticklabels(ax.get_xmajorticklabels(), fontsize=14)
    ax.set_yticklabels(ax.get_yticks(), fontsize=14)
    if logarithmic:
        plt.yscale("log")
    else:
        outfile = outfile.replace(".png", "-no-log.png")
    plt.tight_layout()
    plt.savefig(outfile)
    plt.clf()
    plt.close()


if __name__ == "__main__":
    main()
