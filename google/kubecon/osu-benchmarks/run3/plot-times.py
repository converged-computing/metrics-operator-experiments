import pandas
import matplotlib.pylab as pylab
import seaborn as sns
import json
import sys
import os

# Times are here
here = os.path.dirname(os.path.abspath(__file__))
times_file = os.path.join(here, "times.log")

# Output images
outdir = os.path.join(here, "img")
if not os.path.exists(outdir):
    os.makedirs(outdir)

df = pandas.read_csv(times_file)
df.columns = ["metric", "seconds", "nodes"]

# Draw a nested boxplot to show bills by day and time
sns.set(font_scale=0.8)

# Make a plot for each metric
metrics = df.metric.unique()
for metric in metrics:
    print(f"Plotting OSU Benchmark {metric}")
    subset = df[df.metric == metric]
    plt = sns.scatterplot(
        x="nodes", y="seconds", hue="nodes", data=subset, palette="muted"
    )
    # When we have > 1 point
    # plt = sns.boxplot(x="nodes", y="seconds", hue="nodes", palette=["m", "g"], data=subset)
    plt.set(title=f"{metric} time (seconds) to run across c2d-standard-2 sizes")
    handles, labels = plt.get_legend_handles_labels()
    fig = plt.get_figure()
    fig.savefig(os.path.join(outdir, f"osu_benchmark_{metric}.png"))
    pylab.close()


# EXTRA


def plot_results(results, img):
    """
    Plot result images to file
    """
    # Create a data frame for each result type
    dfs = {}
    idxs = {}
    columns = {}
    for entry in results:
        for result in entry["data"]:
            title = result["header"][0].replace("#", "").strip()
            slug = title.replace(" ", "-")
            if slug not in dfs:
                dfs[slug] = pandas.DataFrame(columns=result["columns"])
                idxs[slug] = 0
                columns[slug] = {"x": result["columns"][0], "y": result["columns"][1]}
            for datum in result["matrix"]:
                dfs[slug].loc[idxs[slug], :] = datum
                idxs[slug] += 1

    # Save each completed data frame to file and plot!
    for slug, df in dfs.items():
        print(f"Preparing plot for {slug}")

        # Save to data file
        df.to_csv(os.path.join(img, f"{slug}.csv"))

        # Separate x and y - latency (y) is a function of size (x)
        x = columns[slug]["x"]
        y = columns[slug]["y"]

        # Save to data file
        title = slug.replace("-", " ")

        # for sty in plt.style.available:
        ax = sns.lineplot(
            data=df, x=x, y=y, markers=True, dashes=True, errorbar=("ci", 95)
        )
        plt.title(title)
        ax.set_xlabel(x + " logscale", fontsize=16)
        ax.set_ylabel(y + " logscale", fontsize=16)
        ax.set_xticklabels(ax.get_xmajorticklabels(), fontsize=14)
        ax.set_yticklabels(ax.get_yticks(), fontsize=14)
        plt.xscale("log")
        plt.yscale("log")
        plt.tight_layout()
        plt.savefig(os.path.join(img, f"{slug}.png"))
        plt.clf()
        plt.close()
