# Spot Instance Potpourri

> Really trying to make a potpourri this time!

We didn't have much luck choosing spot to improve upon the HPC family of instances, nor did we have luck
trying to choose a matching cohort of smaller instances. Instead, we need to move into the optimizer approach,
actually trying to solve an equation! I'm relatively new at this but I will do my best. The details
are in my research notes (private) but I'll show usage here. Note that you need AWS credentials exported in the environment, as we use the spot instance scoring and pricing APIs.

## Data Generation

The [spot_instances.py](spot_instances.py) can be used to generate data:

```bash
$ python spot_instances.py gen
```

That will generate the data file [instances-aws.csv](instances-aws.csv) that we derive current spot prices for.
If you are about to run an experiment, it's recommended to re-generate this file.

## Optimize

The script here takes the following approach ("algorithm" if we can call it that!) I wrote it so, it can't be that complex... I like simple things :P You can read the comments in the script for implementation details. 

### Algorithm

1. Start with a user selection to filter down instances (e.g., hypervisor, GPU, bare metal). This defaults to x86.
2. Take a user selection of cores (required). This is the number we are striving to get across our instance potpurri.
3. Setup. Calculate:
  - Mean price across all instances types for one cores size (e.g., 1,2 ... 128)
  - The number of instance types available for a size (fewer types typically means higher risk)
  - The minimum number of instances needed for each core size, if the entire job uses it (for spot scores)
4. Use spot scores to estimate min and max bounds for each core size:
  - For each core size and min count needed:
    - If the count is > 50, set exactly to 50 (the spot score API does not accept greater than 50)
    - Do a query to the spot score API with the region, instance list we have for the size, and current count.
    - If the score is equal to or above the user set minimum (a risk tolerance) we accept it, and save the count.
    - If the score is less than the user set minimum, it's too high risk, we decrease count by 1/3 and try again
   - At the end of the procedure above, we prepare a list of bounds (min 0, max the count determined) that takes into account the risk tolerance for our ability to get instances.
5. We want a a subset of instances s.t. `count(instances) < max_instances, and sum(cores) >= asked_cores`
6. Define variables for `scipy.optimize.linalg_prog` (see script for these implementation details).
  - row X: the row of costs, in the order of the instance sizes
  - matrix A: 2 rows, 1st: all 1s (counts the instances) 2nd: cores per instance (negative because inequality flipped)
  - b_ub has max number of instances (we set to number cores, assuming smallest 1 core/instance) and negative minimum number of cores (again inequality is flipped)
  - note that we could have a third row if we want to set an upper bound on cores 
  - we set `integrality` to say the answer must be integer. 
6. Run `scipy.optimize.linprog` with this first set of parameters. It typically chooses based on the min cost per core.
  - The `result.x` is a vector of coeffients, where each represents the number of one of the sizes selected.
7. Generate remainder of results requested by used (e.g., the next 19 if 20 was wanted)
  - Find the first case of where the previous result had an x coefficient != 0 (this indicated selecting an instance)
  - Reduce the bounds of that instance max by 1 (to force not selecting that count). 
  - If the bound is already 0, move on to the next coefficient.
8. Print results to the terminal as they go, and save complete results to json (ordered index 0 as the first / best).

In the above, we choose a next best result based on constraining the space a little bit (meaning, we don't allow the equation to select the same number of the instance type, maybe forcing it to select a slightly lesser solution). 

Note that the above assumes that we always allow selecting from the full set of instances that we know about at the moment, which would be selected above some minimum price from the main table (this is not added to the script yet, but for experiments would be). This is also different from the batch approach we originally imagined to force selecting more rare instances by severely limiting this set.

Also be careful about the result object - the nubmers are supposed to be integers (and they look like it) but closer inspection they are floats REALLY close to integers, so I do `int(math.ceil(<number>))`

### Usage

```bash
python test_optimize.py --help
```
```console
usage: test_optimize.py [-h] [--hypervisor HYPERVISOR] [--min-score MIN_SCORE] [--region REGION] [--outfile OUTFILE]
                        [--linprog-method LINPROG_METHOD] [--results RESULTS] [--bare-metal] [--has-gpu] [--arch ARCH]
                        cores

Spot Instance Equation Tester!

positional arguments:
  cores                 cores needed for analysis (minimum)

options:
  -h, --help            show this help message and exit
  --hypervisor HYPERVISOR
                        filter to this hypervisor
  --min-score MIN_SCORE
                        the minimum score to allow for a spot instance request (risk level), defaults to 9 lowest risk
  --region REGION       region to select instances in (defaults to us-east-2)
  --outfile OUTFILE     save json results (for N results) to this json file!
  --linprog-method LINPROG_METHOD
                        scipy.optimizer.linprog method to use (defaults to highs)
  --results RESULTS     number of results (combinations to present) defaults to 20
  --bare-metal          select bare metal instances
  --has-gpu             select GPU instances
  --arch ARCH           architecture to select (defaults to x86_64
```

Let's test for a size 512 (and the rest, using the defaults) and be brave and ask for 100 results (to see weird patterns), also because the spot score API is fairly limited.

```bash
python test_optimize.py 512 --results 100
```

You can view the demo:

[![asciicast](https://asciinema.org/a/625334.svg)](https://asciinema.org/a/625334)

To step back, 512 cores is the same as the hpc7g.

- hpc7g: 64 physical cores, $1.68 per hour * 8 nodes == $13.44/hour for 512 tasks
- hpc6a: 96 physical cores, $2.88 per hour * 8 nodes == $23.04/hour for 768 tasks

While we still just have one option that is under the hpc price, with my previous approach, the next solution lowest price was ~$22. With this approach, even with some generalizing, we found a better balance to select an instance core type based on those available (for example, if only 3-4 instance types are available, we might select at most 1 or 2). And this can be further tweaked. Here is the listing of combinations we found that are lower than the next lowest solution (meaning the optimizer found these for us, and it would have been hard to do manually).

```console
⭐️ Suggested top request (accounting for price and spot scores):
  => Result: 💰️ $12.4 for 1 instances.

Calculating remainder of results (total {args.results})
  => Result: 💰️ $14.0 for 5 instances.
  => Result: 💰️ $16.4 for 5 instances.
  => Result: 💰️ $18.0 for 2 instances.
  => Result: 💰️ $20.2 for 4 instances.
  => Result: 💰️ $20.4 for 3 instances.
  => Result: 💰️ $20.8 for 4 instances.
  => Result: 💰️ $21.0 for 4 instances.
  => Result: 💰️ $21.1 for 4 instances.
  => Result: 💰️ $21.6 for 3 instances.
  => Result: 💰️ $21.7 for 3 instances.
  => Result: 💰️ $21.8 for 3 instances.
```

Maybe we didn't solve the spot instance problem, but this is some start. I'm pretty proud of myself for doing linear programming! 😆️
