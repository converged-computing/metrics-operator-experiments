import argparse
import pandas
from metricsoperator.metrics import get_metric
from metricsoperator import utils as utils
import matplotlib.pyplot as plt
import seaborn as sns
import fnmatch
import json
import os
import re

plt.style.use("bmh")
here = os.path.dirname(os.path.abspath(__file__))


def get_parser():
    parser = argparse.ArgumentParser(
        description="Plot OSU Benchmarks",
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


axes_default = {"x": "Size"}


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
        if "test" in filename or "nodes" in filename or "cache" in filename:
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
    results = parse_data(files)

    # Save raw results (and data frames for each)
    save_data(results, outdir)
    plot_results(results, outdir)


def save_data(results, outdir):
    """
    Save all data in results to output directory.
    """
    utils.write_json(results["iters"], os.path.join(outdir, "iterations.json"))
    utils.write_json(results["columns"], os.path.join(outdir, "columns.json"))

    # Full dataframes with results
    for name, df in results["results"].items():
        df.to_csv(os.path.join(outdir, f"{name}-4-to-128.csv"))

        # Show (and save) grouped by data) (skip those without numberic like osu_hello)
        try:
            group = df.groupby("pods").mean()
            print(group)
            group.to_csv(os.path.join(outdir, f"{name}-groups-4-to-128.csv"))
        except:
            print(f"Skipping {name}, likely not numeric data.")

    # Times to do the runs (wrappers)
    if "times" not in results:
        return

    for name, df in results["times"].items():
        df.to_csv(os.path.join(outdir, f"{name}-time-wrapper-seconds-4-to-128.csv"))

        # Show (and save) grouped by data)
        group = df.groupby("pods").mean()
        print(group)
        group.to_csv(
            os.path.join(outdir, f"{name}-time-wrapper-seconds-groups-4-to-128.csv")
        )


def parse_data(files):
    """
    Given a listing of files, parse into results data frame
    """
    # Derive metric handle (empty without a spec)
    m = get_metric("network-osu-benchmark")()

    # Read in output files and organize data frames by result title
    results = {}
    timed = {}
    timed_idxs = {}
    idxs = {}
    columns = {}

    # Lookup of iterations by size and metric
    iters = {}
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

            # Now we can parse the data
            for r in result["data"]:

                # Look up the iteration from before
                metric_name = slug = os.path.basename(r["command"])
                uid = f"{pods}-{metric_name}"
                if uid not in iters:
                    iters[uid] = 0
                iteration = iters[uid]
                iters[uid] += 1

                # We are collapsing data across sizes, so all data for one metric is in
                # one data frame, 4 up to 64
                if slug not in results:
                    results[slug] = pandas.DataFrame(
                        columns=r["columns"] + ["iter", "pods"]
                    )
                    idxs[slug] = 0
                    columns[slug] = r["columns"]

                for datum in r["matrix"]:
                    try:
                        results[slug].loc[idxs[slug], :] = datum + [iteration, pods]
                    except Exception as e:
                        raise ValueError(f"There was an issue parsing {slug}: {e}")
                    idxs[slug] += 1

                # Do we have timed data? add it.
                if "timed" in r and slug not in timed:
                    timed[slug] = pandas.DataFrame(
                        columns=["real", "user", "sys", "iter", "pods"]
                    )
                    timed_idxs[slug] = 0

                if "timed" in r:
                    # Convert each time into seconds
                    real = convert_time(r["timed"]["real"])
                    user = convert_time(r["timed"]["user"])
                    systime = convert_time(r["timed"]["sys"])
                    timed[slug].loc[timed_idxs[slug], :] = [
                        real,
                        user,
                        systime,
                        iteration,
                        pods,
                    ]
                    timed_idxs[slug] += 1

    print(
        "Overview: iterations should be the same for each (20) across sizes 4, 8, 16, 32, 64, 128"
    )
    print(json.dumps(iters, indent=4))
    return {"iters": iters, "results": results, "columns": columns, "times": timed}


def convert_time(timestamp):
    """
    Convert a timestamp into pure seconds

    E.g., it's usually in minutes and seconds or just seconds
    261m44.303s <- big example
    0m6.873s    <- little example
    """
    minutes, seconds = timestamp.split("m", 1)
    minutes = float(minutes)
    seconds = float(seconds.strip("s"))
    return minutes * 60 + seconds


def plot_results(data, outdir):
    """
    Make plots for each result item.
    """
    # Unwrap data
    results = data["results"]
    columns = data["columns"]
    times = data.get("times") or {}

    # Plot times for each
    for slug, df in times.items():
        df = df.rename(columns={"pods": "nodes"})
        x = "nodes"
        y = "real"
        plot_single(df, x, y, f"{slug}-times-seconds", columns, outdir)

    # Now plot each dataframe
    for slug, df in results.items():
        print(f"Plotting boxplot for {slug}")

        # Be more explicit we have the entire node for one pod
        df = df.rename(columns={"pods": "nodes"})

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
                plot_single(df, x, y, f"{slug}-{suffix}", columns, outdir)

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


def plot_single(df, x, y, slug, columns, outdir):
    """
    Plot two values, and and y, over time
    """
    ax = sns.boxplot(data=df, x=x, y=y, hue="nodes", palette="muted")
    outfile = os.path.join(outdir, f"{slug}-hist-4-to-128.png")
    make_plot(ax, slug=slug, outfile=outfile, xlabel=x)


def plot_pairs(df, slug, columns, outdir):
    """
    Plot two values, and and y, over time
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
    outfile = os.path.join(outdir, f"{slug}-line-4-to-128.png")
    make_plot(ax1, slug=slug, outfile=outfile, xlabel=xlabel, ylabel=ylabel)

    ax2 = sns.boxplot(data=df, x=x, y=y, hue="nodes", palette="muted")
    outfile = os.path.join(outdir, f"{slug}-box-4-to-128.png")
    make_plot(ax2, slug=slug, outfile=outfile, xlabel=xlabel, ylabel=ylabel)


def make_plot(ax, slug, outfile, xlabel=None, ylabel=None):
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
    plt.yscale("log")
    plt.tight_layout()
    plt.savefig(outfile)
    plt.clf()
    plt.close()


if __name__ == "__main__":
    main()
