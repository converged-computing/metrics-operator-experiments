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
# Example for size 16, 15 iterations x 3 (likely could do this more frequently)
export GOOGLE_PROJECT=myproject
for i in 1 2 3; do
    echo "🥞️ Running top level iteration ${i}"
    time /bin/bash ./collect.sh ${GOOGLE_PROJECT} 18 ./crd/metrics-16-subset.yaml 15
done
```

I wound up reducing this to 3 - 5x took ~2 hours sometimes.

```bash
# Example for size 16, 5 iterations x 3 (likely could do this more frequently)
export GOOGLE_PROJECT=myproject
for i in 1 2 3; do
    echo "🥞️ Running top level iteration ${i}"
    time /bin/bash ./collect.sh ${GOOGLE_PROJECT} 18 ./crd/metrics-16.yaml 3
done
```

And then after our meeting, we decided to reduce the number of things to run (down to 3) and increase collections back to 20
(and I wrote a wrapper script to time this):

```bash
time /bin/bash ./collect-set.sh ${GOOGLE_PROJECT}
```

These smaller experiments are running and I'll assess if it's a better setup. Ideally I'd like to do 2 times during the week, possibly
once during the weekend (varying Saturday / Sunday) and then each time, in the morning / late afternoon / evening (based on when I'm awake)

## Automation

TLDR: I can run an hourly cron job on a small server as follows:

```
# Run 3 clusters at a probability of 2% of running each run
python3 random-run.py -p 2.0 -c 3 --project ${GOOGLE_PROJECT}

# But we can run (to source environment to) like:
/bin/bash /path/to/metrics-operator-experiments/google/kubecon/osu-benchmarks/temporal/random-run.sh PROJECT
```

And **important** you need to add Kubernetes admin to your GCP service account.

### Instance

Setting up the environment.

This is an e2 shared core (2vcpu, 4GB memory instance with 50GB disk)
I decided to scp data from there to my local machine instead of git pushing

```bash
sudo apt-get update && sudo apt-get install -y git python3-pip python3-venv cron
sudo apt-get install google-cloud-sdk-gke-gcloud-auth-plugin
git clone https://github.com/converged-computing/metrics-operator-experiments
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" 
chmod +x ./kubectl
sudo mv ./kubectl /usr/local/bin/
```

Then setup the env and do a test run

```bash
cd ~/metrics-operator-experiments/google/kubecon/osu-benchmarks/temporal
python3 -m venv env
# metricsoperator was version 0.0.19
pip install metricsoperator seaborn pandas
python3 ./random-run.py -p 2.0 -c 1 --force --project ${GOOGLE_PROJECT}
```

When you are ready to automate, add via crontab -e (use full paths)

```bash
crontab -e
```
```console
0 * * * * /bin/bash /home/youruser/metrics-operator-experiments/google/kubecon/osu-benchmarks/temporal/random-run.sh PROJECT
```

Check status:

```bash
sudo service cron status
```

And then CHECK ON IT REGULARLY to ensure that you are getting
results and there aren't bugs. To copy to a local machine:

```bash
gcloud compute scp --recurse instance-name:~/metrics-operator-experiments/google/kubecon/osu-benchmarks/temporal/data ./data
```

And let's try that out!

### Design

For now I'm going to aim for 6 months. Here is my thinking:

- 3 metrics (in the metrics-16-subset.yaml)
- 20 iterations each
- 3 clusters per run

For the above, for size 16 one cluster takes an hour, so 3 clusters == 3 hours. For 
c2d-standard-2 that is about $5 per run. If we want to totally randomize this, I suspect thje easiest way is to use cron, and to run a script hourly, but then have some probability that it will actually run. Let's aim this to try and spend $1000 over a year (arbitrary and can be stopped or changed). Here is my thinking:

```python
import random

# Tiny simulation of runs
# This will count the number of runs we get
counts = {}

# Number of days we want to cover
days = 365

# Probabilities to test (0.1 to 5) and out of 100
probs = [round(x * 0.1, 2) for x in list(range(30, 0, -1))]

# Assuming we run it once an hour for that many days
for i in range(0, days*24):
    for prob in probs:
        if prob not in counts:
            counts[prob] = {True:0, False:0}

        # Do the run?
        dorun = random.choice(range(0,100)) < prob
        counts[prob][dorun] +=1

# What is the cost per run? (dollars)
cost_per_run = 5

# Show results!
for prob, result in counts.items():
    total_cost = cost_per_run * result[True]
    print(f'Total cost for probabiltiy {prob}% over a year is ${total_cost}')
```
```console
Total cost for probabiltiy 3.0% over a year is $1385
Total cost for probabiltiy 2.9% over a year is $1355
Total cost for probabiltiy 2.8% over a year is $1260
Total cost for probabiltiy 2.7% over a year is $1235
Total cost for probabiltiy 2.6% over a year is $1445
Total cost for probabiltiy 2.5% over a year is $1350
Total cost for probabiltiy 2.4% over a year is $1295
Total cost for probabiltiy 2.3% over a year is $1295
Total cost for probabiltiy 2.2% over a year is $1245
Total cost for probabiltiy 2.1% over a year is $1350  <--- in here somewhere
Total cost for probabiltiy 2.0% over a year is $900   <---
Total cost for probabiltiy 1.9% over a year is $745
Total cost for probabiltiy 1.8% over a year is $795
Total cost for probabiltiy 1.7% over a year is $915
Total cost for probabiltiy 1.6% over a year is $880
Total cost for probabiltiy 1.5% over a year is $960
Total cost for probabiltiy 1.4% over a year is $880
Total cost for probabiltiy 1.3% over a year is $930
Total cost for probabiltiy 1.2% over a year is $845
Total cost for probabiltiy 1.1% over a year is $870
Total cost for probabiltiy 1.0% over a year is $535
Total cost for probabiltiy 0.9% over a year is $370
Total cost for probabiltiy 0.8% over a year is $405
Total cost for probabiltiy 0.7% over a year is $410
Total cost for probabiltiy 0.6% over a year is $375
Total cost for probabiltiy 0.5% over a year is $440
Total cost for probabiltiy 0.4% over a year is $375
Total cost for probabiltiy 0.3% over a year is $460
Total cost for probabiltiy 0.2% over a year is $365
Total cost for probabiltiy 0.1% over a year is $365
```

So I think if we ran this hourly, every day, and there is a 2% chance of it running, this
would give us a good rate.  We would get about 280 samples.

```bash
{3.0: {True: 277, False: 8483},
 2.9: {True: 271, False: 8489},
 2.8: {True: 252, False: 8508},
 2.7: {True: 247, False: 8513},
 2.6: {True: 289, False: 8471},
 2.5: {True: 270, False: 8490},
 2.4: {True: 259, False: 8501},
 2.3: {True: 259, False: 8501},
 2.2: {True: 249, False: 8511},
 2.1: {True: 270, False: 8490},
 2.0: {True: 180, False: 8580}, <---
 1.9: {True: 149, False: 8611},
 1.8: {True: 159, False: 8601},
 1.7: {True: 183, False: 8577},
 1.6: {True: 176, False: 8584},
 1.5: {True: 192, False: 8568},
 1.4: {True: 176, False: 8584},
 1.3: {True: 186, False: 8574},
 1.2: {True: 169, False: 8591},
 1.1: {True: 174, False: 8586},
 1.0: {True: 107, False: 8653},
 0.9: {True: 74, False: 8686},
 0.8: {True: 81, False: 8679},
 0.7: {True: 82, False: 8678},
 0.6: {True: 75, False: 8685},
 0.5: {True: 88, False: 8672},
 0.4: {True: 75, False: 8685},
 0.3: {True: 92, False: 8668},
 0.2: {True: 73, False: 8687},
 0.1: {True: 73, False: 8687}}
```

### Results

**TODO**

You can see a breakdown of results as follows:

```bash
python3 plot-times.py --results ./data --out ./img
```

We will need to change this view when there are more data points!

