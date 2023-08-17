#!/usr/bin/env python3

import os
import metricsoperator.utils as utils
import seaborn as sns
import matplotlib.pyplot as plt
import pandas

here = os.path.abspath(os.path.dirname(__file__))
data_dir = os.path.join(here, "data")

plt.style.use("bmh")


def get_columns(results):
    """
    Get columns from a single job
    """
    job = results["data"][0]["jobs"][0]
    sections = {"read": job["read"], "write": job["write"], "trim": job["trim"]}
    columns = []
    for name, section in sections.items():
        for field, value in section.items():
            if isinstance(value, (float, int)):
                columns.append(f"{name}_{field}")
    return columns


def main():
    # Sections will be consistent across results
    columns = None
    results = {}

    # First read in the raw data
    for instance in os.listdir(data_dir):
        if not os.path.isdir(os.path.join(data_dir, instance)):
            continue
        for filename in os.listdir(os.path.join(data_dir, instance)):
            if not filename.endswith(".json"):
                continue
            fullpath = os.path.join(data_dir, instance, filename)
            res = utils.read_json(fullpath)
            results[fullpath] = {"instance": instance, "data": res}

            # Get fields from first file (should all be the same)
            if not columns:
                columns = get_columns(res)

    # Create a data frame
    cols = ["uid", "storage", "instance", "size", "blocksize"]
    df = pandas.DataFrame(columns=cols + columns)

    # Get column names for some random metrics that maybe are useful?
    idx = 0
    for filename, data in results.items():
        _, iteration, size, blocksize = filename.replace(".json", "").rsplit("-", 3)
        res = data["data"]
        instance = data["instance"]
        job = res["data"][0]["jobs"][0]
        sections = {"read": job["read"], "write": job["write"], "trim": job["trim"]}
        row = {}
        # This assumes in the same order
        for name, section in sections.items():
            for field, value in section.items():
                if isinstance(value, (float, int)):
                    row[f"{name}_{field}"] = value
        df.loc[idx, cols + list(row.keys())] = [
            iteration,
            "filestore",
            instance,
            int(size.replace('G', '')),
            int(blocksize.replace('k', '')),
        ] + list(row.values())
        idx += 1

    # Save data
    df.to_csv(os.path.join(data_dir, "data-filestore.csv"))

    # And plot!
    plot_results(df)


def plot_results(df):
    """
    Plot results to boxplots. Maybe we should have heatmaps in here too?
    """
    # Directory for plotting results
    img = os.path.join(here, "img")
    if not os.path.exists(img):
        os.makedirs(img)

    # Assemble a data frame with all the result types
    for column in df.columns:
        if column in ["uid", "storage", "instance", "size", "blocksize"]:
            continue
        if df[column].sum() == 0:
            print(f"Metric {column} is all zeros, skipping.")
            continue

        # Save to data file
        title = f"Result for {column}"
        slug = column.replace(" ", "-")

        # for sty in plt.style.available:
        # Do first based on size
        ax = sns.boxplot(data=df, x="instance", y=column, hue="size")
        plt.title(title + " by Size (G)")
        ax.set_xlabel("instance type", fontsize=16)
        ax.set_ylabel(column, fontsize=16)
        ax.set_xticklabels(ax.get_xmajorticklabels(), fontsize=14)
        ax.set_yticklabels(ax.get_yticks(), fontsize=14)

        # Make sure we round a bit so it's prettier
        ylabels = ["{:,.2f}".format(x) for x in ax.get_yticks()]
        ax.set_yticklabels(ylabels)

        plt.tight_layout()
        plt.savefig(os.path.join(img, f"{slug}-instance-type.png"))
        plt.clf()

        # And blocksize
        ax = sns.boxplot(data=df, x="instance", y=column, hue="blocksize")
        plt.title(title + " by Block Size (k)")
        ax.set_xlabel("instance type", fontsize=16)
        ax.set_ylabel(column, fontsize=16)
        ax.set_xticklabels(ax.get_xmajorticklabels(), fontsize=14)
        ax.set_yticklabels(ax.get_yticks(), fontsize=14)
        ylabels = ["{:,.2f}".format(x) for x in ax.get_yticks()]
        ax.set_yticklabels(ylabels)
        plt.tight_layout()
        plt.savefig(os.path.join(img, f"{slug}-block-size.png"))
        plt.clf()

        # Now do per instance type
        for instance in df.instance.unique():
            subset = df[df.instance == instance]
            ax = sns.boxplot(data=subset, x="blocksize", y=column, hue="size")
            plt.title(title + " " + instance.capitalize() + " Size vs. Blocksize")
            ax.set_xlabel("Block Size (k)", fontsize=16)
            ax.set_ylabel(column, fontsize=16)
            ax.set_xticklabels(ax.get_xmajorticklabels(), fontsize=14)
            ax.set_yticklabels(ax.get_yticks(), fontsize=14)
            ylabels = ["{:,.2f}".format(x) for x in ax.get_yticks()]
            ax.set_yticklabels(ylabels)
            plt.tight_layout()
            plt.savefig(os.path.join(img, f"{instance}-{slug}-block-size.png"))
            plt.clf()

            ax = sns.boxplot(data=subset, x="size", y=column, hue="blocksize")
            plt.title(title + " " + instance.capitalize() + " Blocksize (k) vs. Size (G)")
            ax.set_xlabel("Size (G)", fontsize=16)
            ax.set_ylabel(column, fontsize=16)
            ax.set_xticklabels(ax.get_xmajorticklabels(), fontsize=14)
            ax.set_yticklabels(ax.get_yticks(), fontsize=14)
            ylabels = ["{:,.2f}".format(x) for x in ax.get_yticks()]
            ax.set_yticklabels(ylabels)
            plt.tight_layout()
            plt.savefig(os.path.join(img, f"{instance}-{slug}-size.png"))
            plt.clf()
        plt.close()


if __name__ == "__main__":
    main()
