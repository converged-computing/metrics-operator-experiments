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
# usage: ./collect.sh <project> <size> <metrics yaml> <iterations>
time bash ./collect.sh llnl-flux 34 ./crd/metrics-32.yaml
```
In the above, iterations is optional. For size, it should be 2 nodes larger than you need (one for JobSet and one for
the Metrics Operator). As an example, to run three times in a row (to assess variability of clusters close together)

```bash
# Example for size 32, 5 iterations x 3
export GOOGLE_PROJECT=myproject
for i in 1 2 3; do
    ./collect.sh ${GOOGLE_PROJECT} 34 ./crd/metrics-32.yaml 5
done
```

Notes from testing (under [data/test](data/test), which I killed a little bit in):

 - 20 iterations is probably too many for this setup
 - 5 iterations x 3 might be more reasonable for one running loop.
 - We could even drop down to size 16 and then 10 iterations?
 - We will get in trouble more for size 32 if we get a slow cluster
 - There is a 60 second sleep, always, to wait for network (we can't get around that), maybe could reduce a little but would be unwise.

```bash
# Example for size 16, 5 iterations x 3 (likely could do this more frequently)
export GOOGLE_PROJECT=myproject
for i in 1 2 3; do
    echo "🥞️ Running top level iteration ${i}"
    time /bin/bash ./collect.sh ${GOOGLE_PROJECT} 18 ./crd/metrics-16.yaml 5
done
```

These smaller experiments are running and I'll assess if it's a better setup. Ideally I'd like to do 2 times during the week, possibly
once during the weekend (varying Saturday / Sunday) and then each time, in the morning / late afternoon / evening (based on when I'm awake)

### Results

You can see a breakdown of results as follows:

```bash
python plot-times.py --results ./data --out ./img
```

We will need to change this view when there are more data points!

