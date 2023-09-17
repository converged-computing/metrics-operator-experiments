# OSU Temporal Experiments

After noticing variability between [run4](run4) and before, I want to do an experiment that
looks at temporal variability, meaning if we create a cluster at different times of the day
or different times of the week, does this influence the times we see? For each timepoint,
I'll create one cluster.

Sizes cost / hour:

 - 32 (34 nodes): $3.1/hour.

## OSU Benchmarks

Since we want this entirely automated, the run (including creation of the cluster and deletion) is done
by a single script. You should ensure that your Python environment with the metricsoperator is sourced
before running this. E.g.,

```bash
source /path/to/env/bin/activate
pip install -r requirements.txt
```

Then you can run the script. it will automate running a command for a size 32 cluster, saving
nodes, and output organized by day and time.

```bash
# usage: ./collect.sh <project> <size> <metrics yaml>
time bash ./collect.sh llnl-flux 34 ./crd/metrics-32.yaml
```

For size, it should be 2 nodes larger than you need (one for JobSet and one for
the Metrics Operator).


### Results

TBA

```bash
python plot-times.py --results ./data --out ./img
```


