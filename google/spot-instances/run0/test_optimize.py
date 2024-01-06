#!/usr/bin/env python3

# Testing using scipy.minimize
# pip install scipy

import argparse
import copy
import math
import os
import random
import sys

import cloudselect.utils as utils
import scipy.optimize
from cloudselect.main import Client

here = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, here)

import spot_instances as spot_cli  # noqa

# This data file must exist, it has a full price table
data_file = os.path.join(here, "instances-google.csv")

# Exit early if we haven't generated the data
if not os.path.exists(data_file):
    sys.exit(f"Cannot find {data_file}! Run spot_instances.py gen first.")


def get_parser():
    parser = argparse.ArgumentParser(
        description="Spot Instance Equation Tester!",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("cores", help="cores needed for analysis (minimum)", type=int)
    parser.add_argument(
        "--min-score",
        help="the minimum score to allow for a spot instance request (risk level), defaults to 9 lowest risk",
        type=int,
        default=9,
    )
    parser.add_argument(
        "--region",
        help="region to select instances in (defaults to us-central1)",
        default="us-central1",
    )
    parser.add_argument(
        "--vcpu-quota",
        dest="quota",
        help="global vCPU quota to use for instance types",
        default=500,
        type=int
    )
    parser.add_argument(
        "--outfile",
        help="save json results (for N results) to this json file!",
        default="spot-instance-choices.json",
    )
    parser.add_argument(
        "--linprog-method",
        help="scipy.optimizer.linprog method to use (defaults to highs)",
        default="highs",
    )
    parser.add_argument(
        "--results",
        help="number of results (combinations to present) defaults to 20",
        default=20,
        type=int,
    )
    parser.add_argument(
        "--randomize-by",
        dest="randomize",
        help="how many random bounds to change when cannot find solution",
        default=20,
        type=int,
    )
    parser.add_argument(
        "--has-gpu",
        help="select GPU instances",
        default=False,
        action="store_true",
    )
    return parser


class PotpourriOptimizer:
    def __init__(
        self,
        cores,
        data_file,
        has_gpu=False,
        region="us-central1",
        linprog_method="highs",
        randomize_by=20,
        vcpu_quota=500,
    ):
        """
        The Potpourri optimizer holds a data frame of instances to
        select from, current bounds, parameters, and the optimizer function.
        """
        self.cores = cores
        self.region = region
        self.linprog_method = linprog_method
        self.randomize_by = randomize_by
        self.df = spot_cli.select_instances(data_file, has_gpu=has_gpu)
        self.vcpu_quota = vcpu_quota

        # Calculate all values we need on setup. Again, we assume that the optimizer is
        # not allowed to change values mid-usage (without creating a new instance)
        self.setup()

        # Calculate max instances of each type based on 500 vcpu limit each
        self.calculate_limits()

        # Initialize bounds
        self.set_params()

    def run(self, reset_bounds=False, random_decrement=False):
        """
        Run the algorithm!
        """
        
        if reset_bounds:
            self.bounds = copy.deepcopy(self.original_bounds)

            # If we allow a random decrement, find one
            if random_decrement:
                how_many = random.choice(range(20))
                count = 0
                while count < how_many:
                    # Select a random idx
                    idx = random.choice(range(len(self.bounds)))
                    if self.bounds[idx][1] <= 0:
                        continue
                    self.bounds[idx] = (0, self.bounds[idx][1] - 1)
                    count += 1

        # Note that we can set a callback to print steps
        return scipy.optimize.linprog(
            self.costs,
            A_ub=self.A,
            b_ub=self.b_ub,
            bounds=self.bounds,
            integrality=self.integrality,
            method=self.linprog_method,
        )

    def set_params(self):
        """
        Set initial parameters. Aside from bounds (that can be reset)
        these do not change.
        """
        self.set_bounds()

        # https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.linprog.html
        # I think we want a subset of instances s.t.:
        # count(instances) < max_instances, and sum(cores) > asked_cores
        # and we have to set max_instances across a range, because the optimization
        # will always choose smaller ones! They are always cheaper (weird)
        # Can this just be a linear problem?
        #   x is the number of instances of each type
        #   c is the cost of each type of instance
        #   l and u are min and max instances of each type
        #   A can be a row matrix of all 1s
        # A * x = [1, 1, ..., 1] [x_1, x_2, ... x_N]^T = x_1 + x_2 + ... + x_N
        self.costs = list(self.mean_costs.values())

        # Let's set A_ub to a numpy array
        # First row is all ones, this just counts the instances
        A1 = len(self.costs) * [1]

        # second row is negative of the number of cores per instance
        # it has to be negative because inequality has to be flipped
        A2 = [x * -1 for x in self.sizes]
        self.A = [A1, A2]

        # b_ub is a 1-D array with just two values:
        # the maximum number of instances (the same as the cores, if we select sizes of 1)
        # and NEGATIVE the minimum number of cores (again, inequality is flipped)
        self.b_ub = [self.cores, -1 * self.cores]

        # The function assumes less than or equal to, but for cores we want greater or equal to
        # If we want to set an upper bound on cores we would have a third row
        # This would say "Must be 0 or greater (all of them)"
        # bounds = (0, None)
        # But I think we want to bound based on selection of instance types available.

        # Must be integer values
        self.integrality = 1
       
    def set_bounds(self):
        """
        Assemble a min (0) and max instances for each size!
        Note that this goes only up to the size we generated above.
        We could fudge a little bit.
        """
        self.bounds = []
        for size in self.sizes:
            # This means we didn't get a score, which I think can happen if we ask for
            # instances that don't exist for the zone (oops, I did this)...!
            if size not in self.max_instances:
                self.bounds.append((0, 0))
            else:
                self.bounds.append((0, self.max_instances[size]))

        # Save the original bounds for reset later
        self.original_bounds = copy.deepcopy(self.bounds)

    def calculate_limits(self):
        """
        Assume our quota is 500 cores / family.
        
        So for each instance size, basically figure out how many max instances
        we can ask for. This is a separate function if we ever have different quotas
        per instance type.
        """
        self.max_instances = {}
        instance_types = self.df.instance.tolist()
        for instance_type in instance_types: 
            cores = self.df[self.df.instance == instance_type].cores.to_list()[0]            
            self.max_instances[cores] = math.floor(self.vcpu_quota / cores)

    def setup(self):
        """
        Run initial setup, or caching of values we will need later.

        This should only be done once.
        """
        # Calculate the price / cores
        self.df["price_per_core"] = self.df.spot_price / self.df.cores

        # This was just for my viewing
        # sorted_df = df.sort_values(["price_per_core", "cores"])
        self.mean_costs = {}
        self.mean_costs_per_core = {}

        # Let's keep track of the number available for each.
        # We don't generally want to trust a size with less than 4.
        self.available = {}

        # We also will calculate the min number of instances needed for each type
        self.needed_counts = {}

        # Get mean value for each (to minimize)
        # The second was just for my FYI, for example when we don't set bounds,
        # the optimizer chooses 4 x 128, which has the cheapest cost / core
        for core in self.unique_cores:
            self.mean_costs[core] = self.df[self.df.cores == core].spot_price.mean()
            self.mean_costs_per_core[core] = self.df[
                self.df.cores == core
            ].price_per_core.mean()
            self.available[core] = self.df[self.df.cores == core].shape[0]
            # Take a ceiling, having a little extra is OK
            self.needed_counts[core] = math.ceil(self.cores / core)

        # We will use order of sizes to calculate bounds
        self.sizes = list(self.mean_costs.keys())

    def find_highest_cost_index(self, result, ignores):
        """
        Given a result, we want to decrement the max bound for the most
        expensive option cost PER core. This will (hopefully) force the
        algorithm to choose an option with a better cost per core.
        """
        # Determine the most expensive per core hour. First, these are indices of chosen
        # ignores takes into account indices that we need to ignore (e.g, bounds zeroed out)
        chosen_idx = [
            i for i, x in enumerate(result.x) if int(round(x)) != 0 and i not in ignores
        ]
        chosen_sizes = [self.sizes[idx] for idx in chosen_idx]

        # Given the chosen sizes, filter down the mean price per core, and sort highest to lowest
        subset_mppc = {x: self.mean_costs_per_core[x] for x in chosen_sizes}
        subset_mppc = {
            k: v
            for k, v in sorted(
                subset_mppc.items(), key=lambda item: item[1], reverse=True
            )
        }

        # This is the highest price, the size if adjust cheapest
        chosen_size = list(subset_mppc.keys())[0]

        # Return the index of the highest price
        return self.sizes.index(chosen_size)

    @property
    def unique_cores(self):
        """
        Unique quantities of cores, and mean cost by size
        """
        return self.df.cores.unique().tolist()

    def show_result(self, result):
        """
        Helper function to show a result.

        Note that no result data should be stored with this class.
        """
        # One result might have multiple instances
        single_result = {"instances": []}
        total_cost = 0
        total_count = 0

        # Create a unique id so we know if we've seen it before
        uid = ""
        for i, count in enumerate(result.x):
            size = self.sizes[i]

            # IMPORTANT: the result looks like an int, but is a long float
            # This might introduce error, look at again at some point
            count = int(round(count))
            if count != 0:
                if uid:
                    uid += f"-{size}-{count}"
                else:
                    uid = f"{size}-{count}"

                # Cost for this set of instances
                cost_per_instance = round(self.mean_costs[size], 2)
                instances_cost = count * round(cost_per_instance, 2)
                total_cost += instances_cost
                total_count += count
                single_result["instances"].append(
                    {
                        "count": count,
                        "size": size,
                        "total_cores": count * size,
                        "cost_per_instance": cost_per_instance,
                        "instances_cost": instances_cost,
                        "available": self.available[size],
                    }
                )

        single_result["uid"] = uid
        single_result["total_count"] = total_count
        single_result["total_cost"] = total_cost
        total_cost = round(total_cost, 2)
        return single_result


def main():
    """
    Run experiments for lammps, and collect hwloc info.
    """
    # Strategy 1: calculate the cheapest cost / cpu to filter down instance sizes
    # Manually derived equation for now, based on mean prices
    # import the script we have two levels up
    parser = get_parser()

    # If an error occurs while parsing the arguments, the interpreter will exit with value 2
    args, _ = parser.parse_known_args()

    # cores are required!
    if not args.cores:
        sys.exit("Number of cores for analysis is required.")

    # Create a potpourri optimizer! I shall call him "poo"
    poo = PotpourriOptimizer(
        args.cores,
        data_file,
        has_gpu=args.has_gpu,
        region=args.region,
        linprog_method=args.linprog_method,
        randomize_by=args.randomize,
        vcpu_quota=args.quota,
    )

    # Run the initial algorithm! This gives us a first result to start from
    result = poo.run()
    
    # Save json dict of results
    results = []

    # Keep track of results we have seen
    seen = set()

    # The top result is always added, we haven't seen it yet!
    print(result)
    print("\n⭐️ Suggested top request (accounting for price and quotas):")
    for i, count in enumerate(result.x):
        res = poo.show_result(result)
        if res and res["uid"] not in seen:
            seen.add(res["uid"])
            del res["uid"]
            print_result(res)
            results.append(res)

    print(f"\nCalculating remainder of results (total {args.results})")
    args.results -= 1

    # Find the first non-zero, and decrease by one in the bounds
    while args.results > 0:
        # Find the index into sizes (where a choice was made) with the highest cost per core
        # In case we cannot decrement a bound, we allow this to loop
        ignores = set()
        while True:
            idx = poo.find_highest_cost_index(result, ignores)
            bound = poo.bounds[idx]

            # We can't go any lower, we've eliminated this
            if bound[1] <= 0:
                ignores.add(idx)
                continue

            # If we get here, break out of while!
            break

        # If we get here, we have a valid index, and decrease the bound by 1
        poo.bounds[idx] = (bound[0], bound[1] - 1)

        # Calculate the new result (with new bounds)
        # It might have different sets of instances
        result = poo.run()

        # We currently remove the highest cost per core already. This biases to always keep the lowest.
        # This means all solutions will have the lowest cost per core, because we don't want to remove it
        # But if we remove enough more expensive, we eventually run out. When this happens this errors.
        # And we should restore our original bounds, but allow decrement of the cheapest by one
        # This will force other solutions that fill the space of the previous cheapest one
        # If we set it to 0, we could be more aggressive and get very different (more expensive) answers
        if not result.success:
            print("Randomizing...", end="\r")
            result = poo.run(reset_bounds=True, random_decrement=True)

        # If we make it here (success) go back to decrement of max cost instance!
        res = poo.show_result(result)
        if res and res["uid"] not in seen:
            seen.add(res["uid"])
            del res["uid"]
            print_result(res)
            results.append(res)
            args.results -= 1

    print(f"Saving results to {args.outfile}")
    utils.write_json(results, args.outfile)


def print_result(res):
    total_cost = round(res["total_cost"], 1)
    print(f"  => Result: 💰️ ${total_cost} for {len(res['instances'])} instances.")


if __name__ == "__main__":
    main()
