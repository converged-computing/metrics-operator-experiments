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
sys.path.insert(0, here)
from osu import run_parsing_function

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
    plot_results(results, outdir)
    save_data(results, outdir)


def save_data(results, outdir):
    """
    Save all data in results to output directory.
    """
    utils.write_json(results["columns"], os.path.join(outdir, "columns.json"))

    # Full dataframes with results
    for name, df in results["results"].items():
        df.to_csv(os.path.join(outdir, f"{name}-2-to-128.csv"))
        try:
            # Show (and save) grouped by data) (skip those without numberic like osu_hello)
            if "Size" in df.columns:
                group = df.groupby(["nodes", "Size"]).mean()
            else:
                group = df.groupby("nodes").mean()
            print(group)
            group.to_csv(os.path.join(outdir, f"{name}-groups-2-to-128.csv"))
        except:
            print(f"Skipping {name}, likely not numeric data.")

    # Times to do the runs (wrappers)
    if "timed" not in results:
        return

    for name, df in results["timed"].items():
        df.to_csv(os.path.join(outdir, f"{name}-time-wrapper-seconds-2-to-128.csv"))

        # Show (and save) grouped by data)
        group = df.groupby("nodes").mean()
        print(group)
        group.to_csv(
            os.path.join(outdir, f"{name}-time-wrapper-seconds-groups-2-to-128.csv")
        )


def parse_data(files):
    """
    Given a listing of files, parse into results data frame
    """
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
                else:
                    # Don't add empty or ending line
                    if line and not line.startswith("End"):
                        result["data"].append(line)

            # Add the last result
            if result and identifier:
                if identifier not in results[nodes]:
                    results[nodes][identifier] = []
                results[nodes][identifier].append(result)

    # Now for each, artificially assemble into metrics operator result to parse
    final = {}
    idxs = {}
    times_idxs = {}
    times = {}
    columns = {}
    for nodes, result in results.items():
        for metric, r in result.items():

            # We need the first datum for labels, etc. They are all the same
            section = r[0]
            datum = run_parsing_function(
                section["command"] + "\n" + "\n".join(section["data"])
            )
            if metric not in final:
                final[metric] = pandas.DataFrame(columns=datum["columns"] + ["nodes"])
                times[metric] = pandas.DataFrame(
                    columns=list(datum["timed"].keys()) + ["nodes"]
                )
                idxs[metric] = 0
                times_idxs[metric] = 0
                columns[metric] = datum["columns"]

            # Now add each datum section properly
            for section in r:
                datum = run_parsing_function(
                    section["command"] + "\n" + "\n".join(section["data"])
                )
                times[metric].loc[times_idxs[metric], :] = list(datum["timed"].values()) + [nodes]
                times_idxs[metric] += 1
                for row in datum["matrix"]:
                    final[metric].loc[idxs[metric], :] = row + [nodes]
                    idxs[metric] += 1
    return {"raw": results, "results": final, "timed": times, "columns": columns}


def plot_results(data, outdir):
    """
    Make plots for each result item.
    """
    # Unwrap data
    results = data["results"]
    columns = data["columns"]
    times = data.get("timed") or {}

    # Plot times for each
    for slug, df in times.items():
        x = "nodes"
        y = "real"
        plot_single(
            df,
            x,
            y,
            f"{slug}-times-seconds",
            outdir,
            larger_size=False,
            logarithmic=False,
        )

    # Now plot each dataframe
    for slug, df in results.items():
        print(f"Plotting boxplot for {slug}")

        if slug == "osu_latency":
            plot_pairs(df, slug, columns, outdir, logarithmic=False)

        # Nothing to plot for osu_hello
        if slug == "osu_hello":
            continue

        # For ibarrier make a plot for each
        elif slug == "osu_ibarrier":
            x = "nodes"
            for y in columns[slug]:
                suffix = re.sub("([.]| )", "-", y.lower())
                plot_single(df, x, y, f"{slug}-{suffix}", columns, outdir)

        elif slug == "osu_mbw_mr":
            x = "Size"
            for y in columns[slug][1:]:
                suffix = re.sub("([/]|[.]| )", "-", y.lower())
                plot_single(df, x, y, f"{slug}-{suffix}", outdir)

        # min, max, etc
        elif slug == "osu_init":
            x = "nodes"
            y = "avg-ms"
            plot_single(df, x, y, slug, columns, outdir)

        # Just one average latency
        elif slug == "osu_barrier":
            x = "nodes"
            y = columns[slug][0]
            plot_single(df, x, y, slug, columns, outdir)

        elif len(columns[slug]) == 2:
            plot_pairs(df, slug, columns, outdir)
        elif len(columns[slug]) == 1:
            plot_single(df, slug, columns, outdir)
        else:
            raise ValueError(f"We do not know how to plot {slug}")


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


def plot_pairs(df, slug, columns, outdir, logarithmic=True):
    """
    Plot two values, and and y, over time.

    We always plot these with larger size
    """
    # For most, Size is first followed by latency or bandwidth
    if columns[slug][0] == "Size":
        x = columns[slug][0]
        y = columns[slug][1]
    else:
        raise ValueError(f"Unrecognized column pair: {columns[slug]}")

    # For bandwith, higher is better
    memo = "higher is better"
    if "latency" in y.lower():
        memo = "lower is better"
    xlabel = "Packet size (bits)"
    ylabel = y + " " + memo + " (logscale)"

    # Make x int, never actually a float
    df[x] = [int(x) for x in df[x]]
    ax1 = sns.lineplot(
        data=df,
        x=x,
        y=y,
        hue="nodes",
        palette="muted",
        errorbar=("ci", 95),
        markers=True,
        dashes=True,
    )
    outfile = os.path.join(outdir, f"{slug}-line-2-to-128.png")
    make_plot(
        ax1, slug=slug, outfile=outfile, xlabel=xlabel, ylabel=ylabel, larger_size=False
    )

    ax2 = sns.boxplot(data=df, x=x, y=y, hue="nodes", palette="muted")
    outfile = os.path.join(outdir, f"{slug}-box-2-to-128.png")
    make_plot(
        ax2,
        slug=slug,
        outfile=outfile,
        xlabel=xlabel,
        ylabel=ylabel,
        logarithmic=logarithmic,
    )


def make_plot(
    ax, slug, outfile, xlabel=None, ylabel=None, larger_size=True, logarithmic=True
):
    """
    Generic plot making function for some x and y
    """
    # for sty in plt.style.available:
    title = slug.replace("-", " ")
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
