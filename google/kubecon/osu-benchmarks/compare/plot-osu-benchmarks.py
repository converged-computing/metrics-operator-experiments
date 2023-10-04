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
    df_reduce_gcp = read_gcp_data("osu_allreduce-2-to-128-gcp.csv", "cloud-c2d")
    df_reduce_gcp_c3 = read_gcp_data("osu_allreduce-2-to-128-gcp-c3.csv", "cloud-c3")

    # Combine them!
    df_reduce_comb = pandas.concat([df_reduce, df_reduce_gcp, df_reduce_gcp_c3])
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
        title="All Reduce Average Latency Cloud c2d (microseconds) across node sizes",
    )
    plot_pairs(
        df_reduce_gcp_c3,
        hue="nodes",
        x="Size",
        y="Avg Latency(us)",
        slug="allreduce-cloud-c3",
        outdir=outdir,
        title="All Reduce Average Latency Cloud c3 (microseconds) across node sizes",
    )

    # Compare latency
    df_latency = pandas.read_csv(
        os.path.join(here, "osu_latency-2-to-128.csv"), index_col=0
    )
    df_latency["environment"] = "hpc"

    # The other df uses nodes instead of pods, and does not have an iter column
    # Note that we have fewer data points because it took much longer to run here
    df_latency_gcp = read_gcp_data("osu_latency-2-to-128-gcp.csv", "cloud-c2d")
    df_latency_gcp_c3 = read_gcp_data("osu_latency-2-to-128-gcp-c3.csv", "cloud-c3")

    # Ensure they are both the same data type, ug, pandas why
    # df_latency.Size =  pandas.to_numeric(df_latency.Size, downcast='integer')
    # df_latency_gcp.Size = pandas.to_numeric(df_latency_gcp.Size, downcast='integer')
    df_latency_comb = pandas.concat([df_latency, df_latency_gcp, df_latency_gcp_c3])
    df_latency_comb.to_csv(os.path.join(here, "osu_latency-combined.csv"))
    groups = df_latency_comb.groupby(['Size','environment']).mean()
    groups.to_csv(os.path.join(here, "osu_latency-groups-combined.csv"))
    
    print(f"Plotting boxplot for latency")
    plot_pairs(
        df_latency_comb,
        dodge=False,
        x="Size",
        y="Latency(us)",
        slug="latency",
        width=0.5,
        outdir=outdir,
        title="Average Point to Point Latency High Performance Computing System vs. Cloud (microseconds) across node sizes",
    )

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


def plot_single(df, x, y, slug, outdir, larger_size=True, logarithmic=True):
    """
    Plot two values, and and y, over time
    """
    print(slug)
    print(df)
    ax = sns.boxplot(data=df, x=x, y=y, hue="nodes", palette="muted")
    outfile = os.path.join(outdir, f"{slug}-2-to-128.png")
    make_plot(
        ax,
        slug=slug,
        outfile=outfile,
        xlabel=x,
        larger_size=larger_size,
        logarithmic=logarithmic,
    )


def plot_pairs(df, slug, x, y, title, outdir, logarithmic=True, hue="nodes", dodge=True, width=None):
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
        ax2 = sns.boxplot(data=df, x=x, y=y, hue=hue, palette="muted", dodge=dodge, width=width)
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
):
    """
    Generic plot making function for some x and y
    """
    # for sty in plt.style.available:
    sns.set(rc={"figure.figsize": (28, 10)})
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
