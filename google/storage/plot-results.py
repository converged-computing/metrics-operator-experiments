#!/usr/bin/env python3

import argparse
import os
import json
import time
from io import StringIO
from metricsoperator import MetricsOperator
import metricsoperator.utils as utils
import seaborn as sns
import matplotlib.pyplot as plt
import pandas

here = os.path.abspath(os.path.dirname(__file__))
data_dir = os.path.join(here, "data")

plt.style.use("bmh")

def main():

    results = {}

    # First read in the raw data
    for filename in os.listdir(data_dir):
        # skip the 1M size run
        if "1M" in filename:
            continue
        fullpath = os.path.join(data_dir, filename)
        res = utils.read_json(fullpath)
        results[filename] = res

    # Get fields from first file (should all be the same)
    job = list(results.values())[0]['data'][0]['jobs'][0]
    sections = {"read": job['read'], "write": job['write'], 'trim': job['trim']}
    columns = []
    for name, section in sections.items():
        for field, value in section.items():
            if isinstance(value, (float, int)):
                columns.append(f"{name}_{field}")        

    # Create a data frame
    df = pandas.DataFrame(columns=['uid', 'storage'] + columns)

    # Get column names for some random metrics that maybe are useful?
    idx = 0
    for filename, res in results.items():
        storage, ext = filename.rsplit('-', 1)
        uid = int(ext.split('.')[0])
        job = res['data'][0]['jobs'][0]
        sections = {"read": job['read'], "write": job['write'], 'trim': job['trim']}
        row = {}
        # This assumes in the same order
        for name, section in sections.items():
            for field, value in section.items():
                if isinstance(value, (float, int)):
                    row[f"{name}_{field}"] = value
        df.loc[idx, ["uid", "storage"] + list(row.keys())] = [uid, storage] + list(row.values())            
        idx +=1        

    # Save data
    df.to_csv(os.path.join(data_dir, "data.csv"))

    # And plot!
    plot_results(df)

def plot_results(df):
    """
    Plot results to a histogram and matrix heatmap
    """
    # Directory for plotting results
    img = os.path.join(here, "img")
    if not os.path.exists(img):
        os.makedirs(img)
   
    # Assemble a data frame with all the result types
    for column in df.columns:
        if column in ['storage', 'uid']:
            continue
        if df[column].sum() == 0:
            print(f"Metric {column} is all zeros, skipping.")
            continue

        # Save to data file
        title = f"Result for {column}"
        slug = column.replace(' ', '-')
        
        # for sty in plt.style.available:
        ax = sns.boxplot(data=df, x="storage", y=column, hue="storage")
        plt.title(title)
        ax.set_xlabel("storage", fontsize=16)
        ax.set_ylabel(column, fontsize=16)
        ax.set_xticklabels(ax.get_xmajorticklabels(), fontsize=14)
        ax.set_yticklabels(ax.get_yticks(), fontsize=14)
        plt.tight_layout()
        plt.savefig(os.path.join(img, f"{slug}.png"))
        plt.clf()

        # And distribution
        sns.histplot(df, x=column, hue="storage")
        plt.title(f"Histogram for result {column}")
        plt.savefig(
            os.path.join(img, f"{slug}-hist.png"), dpi=300, bbox_inches="tight"
        )
        plt.clf()
        plt.close()


if __name__ == "__main__":
    main()
