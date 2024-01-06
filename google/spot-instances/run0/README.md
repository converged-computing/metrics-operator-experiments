# Spot Instance Potpourri

> Really trying to make a potpourri this time!

Let's try seeing if we can improve upon Google Cloud on demand prices with spot (we could not on AWS)!

## Data Generation

The [spot_instances.py](spot_instances.py) can be used to generate data:

```bash
python spot_instances.py gen
```
```console
⚠️  WARNING: prices are experimental, and often slightly (cents) low (compared to the web UI)
            instance vcpu cores memory_mb    gpu spot_price     price
0     c2-standard-16   16   8.0     65536  False   0.101125  0.843324
1     c2-standard-30   30  15.0    122880  False   0.188651  1.580274
2      c2-standard-4    4   2.0     16384  False   0.026103  0.211653
3     c2-standard-60   60  30.0    245760  False   0.376206  3.159453
4      c2-standard-8    8   4.0     32768  False   0.051111   0.42221
...              ...  ...   ...       ...    ...        ...       ...
1134  n2-standard-48   48  24.0    196608  False   0.639145   3.39603
1135  n2-standard-64   64  32.0    262144  False   0.851828  4.527675
1136   n2-standard-8    8   4.0     32768  False   0.107437  0.566918
1137  n2-standard-80   80  40.0    327680  False   1.064511   5.65932
1138  n2-standard-96   96  48.0    393216  False   1.277194  6.790965

[1139 rows x 7 columns]
```

This will generate `google-prices.csv` that we can use for further steps.
If you are about to run an experiment, it's recommended to re-generate this file.

## Optimize

The script here takes the following approach ("algorithm" if we can call it that!) I wrote it so, it can't be that complex... I like simple things :P You can read the comments in the script for implementation details. 

### Algorithm

- *1.* Start with a user selection to filter down instances. Right now we just take anything with a price and spot price.
- *2.* Take a user selection of cores (required). This is the number we are striving to get across our instance potpurri.
- *3.* Setup. Calculate:
  - Mean price across all instances types for one cores size (e.g., 1,2 ... 128)
  - The number of instance types available for a size (fewer types typically means higher risk)
  - The minimum number of instances needed for each core size, if the entire job uses it (for spot scores)
- *4.* Use spot scores to estimate min and max bounds for each core size:
  - For each core size and min count needed:
    - If the count is > 50, set exactly to 50 (the spot score API does not accept greater than 50)
    - Do a query to the spot score API with the region, instance list we have for the size, and current count.
    - If the score is equal to or above the user set minimum (a risk tolerance) we accept it, and save the count.
    - If the score is less than the user set minimum, it's too high risk, we decrease count by 1/3 and try again
   - At the end of the procedure above, we prepare a list of bounds (min 0, max the count determined) that takes into account the risk tolerance for our ability to get instances.
- *5.* We want a a subset of instances s.t. `count(instances) < max_instances, and sum(cores) >= asked_cores`
- *6*. Define variables for `scipy.optimize.linalg_prog` (see script for these implementation details).
  - row X: the row of costs, in the order of the instance sizes
  - matrix A: 2 rows, 1st: all 1s (counts the instances) 2nd: cores per instance (negative because inequality flipped)
  - b_ub has max number of instances (we set to number cores, assuming smallest 1 core/instance) and negative minimum number of cores (again inequality is flipped)
  - note that we could have a third row if we want to set an upper bound on cores 
  - we set `integrality` to say the answer must be integer. 
- *7.* Run `scipy.optimize.linprog` with this first set of parameters. It typically chooses based on the min cost per core.
  - The `result.x` is a vector of coeffients, where each represents the number of one of the sizes selected.
- *8.* Generate remainder of results requested by used (e.g., the next 19 if 20 was wanted)
  - Find the first case of where the previous result had an x coefficient != 0 (this indicated selecting an instance)
  - Reduce the bounds of that instance max by 1 (to force not selecting that count). 
  - If the bound is already 0, move on to the next coefficient.
- *9.* Print results to the terminal as they go, and save complete results to json (ordered index 0 as the first / best).

In the above, we choose a next best result based on constraining the space a little bit (meaning, we don't allow the equation to select the same number of the instance type, maybe forcing it to select a slightly lesser solution). 

Note that the above assumes that we always allow selecting from the full set of instances that we know about at the moment, which would be selected above some minimum price from the main table (this is not added to the script yet, but for experiments would be). This is also different from the batch approach we originally imagined to force selecting more rare instances by severely limiting this set.

Also be careful about the result object - the nubmers are supposed to be integers (and they look like it) but closer inspection they are floats REALLY close to integers, so I do `int(math.ceil(<number>))`

### Usage

```bash
python test_optimize.py --help
```
```console
Spot Instance Equation Tester!

positional arguments:
  cores                 cores needed for analysis (minimum)

options:
  -h, --help            show this help message and exit
  --min-score MIN_SCORE
                        the minimum score to allow for a spot instance request (risk level), defaults to 9 lowest risk
  --region REGION       region to select instances in (defaults to us-central1)
  --outfile OUTFILE     save json results (for N results) to this json file!
  --linprog-method LINPROG_METHOD
                        scipy.optimizer.linprog method to use (defaults to highs)
  --results RESULTS     number of results (combinations to present) defaults to 20
  --randomize-by RANDOMIZE
                        how many random bounds to change when cannot find solution
  --has-gpu             select GPU instances
```

Let's test for a size 512 (and the rest, using the defaults) and ask for 50 results.

```bash
python test_optimize.py 512 --results 50
```

To step back, 512 tasks is what we needed for running lammps on 8 nodes. This is AWS, yes, but I thought it would be interesting to investigate. Specifically:

- hpc7g: 64 physical cores, $1.68 per hour * 8 nodes == $13.44/hour for 512 tasks
- hpc6a: 96 physical cores, $2.88 per hour * 8 nodes == $23.04/hour for 768 tasks

So based on GCP prices, here is how we can get costs for 512 nodes, and these are per hour.

```console
$ python test_optimize.py 512 --results 50

☝️  Max spot price: 29.70359214641096
👇️ Min spot price: 0.0113877304109589

😸️ Filtered selection of spot:
                  instance  vcpu  cores  memory_mb    gpu  spot_price      price
7            c2d-highcpu-2     2    1.0       4096  False    0.011388   0.087717
21          c2d-standard-2     2    1.0       8192  False    0.013600   0.106374
91                e2-micro     2    1.0       1024  False    0.015081   0.047713
82            e2-highcpu-2     2    1.0       2048  False    0.015979   0.050706
92                e2-small     2    1.0       2048  False    0.015979   0.050706
..                     ...   ...    ...        ...    ...         ...        ...
73   c3d-standard-360-lssd   360  180.0    1474560  False    5.603854  16.481559
61         c3d-highmem-360   360  180.0    2949120  False    7.588611  22.319342
495         m2-megamem-416   416  208.0    6029312  False   17.681144  45.227387
494        m2-hypermem-416   416  208.0    9043968  False   23.692368  60.602133
497        m2-ultramem-416   416  208.0   12058624  False   29.703592  75.976878

[143 rows x 7 columns]

🤓️ Mean (std) of spot price
$1.67 ($3.92)

        message: Optimization terminated successfully. (HiGHS Status 7: Optimal)
        success: True
         status: 0
            fun: 6.846502969882594
              x: [ 8.000e+00  0.000e+00 ...  0.000e+00  0.000e+00]
            nit: -1
          lower:  residual: [ 8.000e+00  0.000e+00 ...  0.000e+00
                              0.000e+00]
                 marginals: [ 0.000e+00  0.000e+00 ...  0.000e+00
                              0.000e+00]
          upper:  residual: [ 4.920e+02  2.500e+02 ...  2.000e+00
                              2.000e+00]
                 marginals: [ 0.000e+00  0.000e+00 ...  0.000e+00
                              0.000e+00]
          eqlin:  residual: []
                 marginals: []
        ineqlin:  residual: [ 4.940e+02  0.000e+00]
                 marginals: [ 0.000e+00  0.000e+00]
 mip_node_count: 1
 mip_dual_bound: 6.846502969882594
        mip_gap: 0.0

⭐️ Suggested top request (accounting for price and quotas):
  => Result: 💰️ $6.8 for 3 instances.

Calculating remainder of results (total 50)
  => Result: 💰️ $6.8 for 4 instances.
  => Result: 💰️ $6.8 for 3 instances.
  => Result: 💰️ $6.8 for 4 instances.
  => Result: 💰️ $7.0 for 2 instances.
  => Result: 💰️ $7.1 for 3 instances.
  => Result: 💰️ $7.1 for 3 instances.
  => Result: 💰️ $7.2 for 3 instances.
  => Result: 💰️ $7.3 for 4 instances.
  => Result: 💰️ $7.3 for 3 instances.
  => Result: 💰️ $7.5 for 3 instances.
  => Result: 💰️ $7.7 for 3 instances.
  => Result: 💰️ $7.8 for 3 instances.
  => Result: 💰️ $8.4 for 3 instances.
  => Result: 💰️ $8.4 for 4 instances.
  => Result: 💰️ $8.5 for 4 instances.
  => Result: 💰️ $8.7 for 3 instances.
  => Result: 💰️ $8.9 for 4 instances.
  => Result: 💰️ $9.2 for 3 instances.
  => Result: 💰️ $10.3 for 2 instances.
  => Result: 💰️ $10.7 for 2 instances.
  => Result: 💰️ $16.0 for 2 instances.
  => Result: 💰️ $20.4 for 3 instances.
  => Result: 💰️ $27.8 for 3 instances.
  => Result: 💰️ $6.8 for 3 instances.
  => Result: 💰️ $6.8 for 4 instances.
  => Result: 💰️ $6.8 for 3 instances.
  => Result: 💰️ $6.8 for 4 instances.
  => Result: 💰️ $7.0 for 2 instances.
  => Result: 💰️ $7.1 for 3 instances.
  => Result: 💰️ $7.1 for 3 instances.
  => Result: 💰️ $7.2 for 3 instances.
  => Result: 💰️ $7.3 for 4 instances.
  => Result: 💰️ $7.3 for 3 instances.
  => Result: 💰️ $7.5 for 3 instances.
  => Result: 💰️ $7.7 for 3 instances.
  => Result: 💰️ $7.8 for 3 instances.
  => Result: 💰️ $8.4 for 3 instances.
  => Result: 💰️ $8.4 for 4 instances.
  => Result: 💰️ $8.5 for 4 instances.
  => Result: 💰️ $8.7 for 3 instances.
  => Result: 💰️ $8.9 for 4 instances.
  => Result: 💰️ $9.2 for 3 instances.
  => Result: 💰️ $10.3 for 3 instances.
  => Result: 💰️ $10.7 for 3 instances.
  => Result: 💰️ $16.0 for 3 instances.
  => Result: 💰️ $20.4 for 3 instances.
  => Result: 💰️ $6.8 for 3 instances.
  => Result: 💰️ $6.8 for 4 instances.
  => Result: 💰️ $6.8 for 3 instances.
Saving results to spot-instance-choices.json
```

I think there might be feet here? To compare again to the AWS prices:

- hpc7g: 64 physical cores, $1.68 per hour * 8 nodes == $13.44/hour for 512 tasks
- hpc6a: 96 physical cores, $2.88 per hour * 8 nodes == $23.04/hour for 768 tasks

If we can pay $6.8/hour for 512 tasks, that would be a huge improvement. Of course the next question is if lammps would run, period, so we need to test that.

### Optimization Tests

 - [spot-instances-choices.json](spot-instances-choices.json): removes the most expensive (by core hour) first and then if reaches local solution, randomizes the original bounds to explore other spaces (this is cool)!
 
For the first, we fall back to an approach that removes the cheapest instead. We could also allow the algorithm to select removing one at random!
