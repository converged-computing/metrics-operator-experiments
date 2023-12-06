#!/usr/bin/env python3

# Testing using scipy.minimize
# pip install scipy

import argparse
import os
import copy
import sys
import math
import scipy.optimize
import random
from cloudselect.main import Client
import cloudselect.utils as utils

here = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, here)

import spot_instances as spot_cli  # noqa

# This data file must exist, it has a full price table
data_file = os.path.join(here, "instances-aws.csv")

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
        "--hypervisor",
        help="filter to this hypervisor",
        default="nitro",
    )
    parser.add_argument(
        "--min-score",
        help="the minimum score to allow for a spot instance request (risk level), defaults to 9 lowest risk",
        type=int,
        default=9,
    )
    parser.add_argument(
        "--region",
        help="region to select instances in (defaults to us-east-2)",
        default="us-east-2",
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
        "--bare-metal",
        help="select bare metal instances",
        default=False,
        action="store_true",
    )
    parser.add_argument(
        "--has-gpu",
        help="select GPU instances",
        default=False,
        action="store_true",
    )
    parser.add_argument(
        "--arch",
        help="architecture to select (defaults to x86_64",
        default="x86_64",
    )
    return parser


class PotpourriOptimizer:
    def __init__(
        self,
        cores,
        data_file,
        bare_metal=False,
        hypervisor="nitro",
        has_gpu=False,
        arch="x86_64",
        region="us-east-2",
        min_score=9,
        linprog_method="highs",
        randomize_by=20,
    ):
        """
        The Potpourri optimizer holds a data frame of instances to
        select from, current bounds, parameters, and the optimizer function.
        """
        # Be generous with initial selection, select specific hypervisor and not bare metal
        # We assume we don't want the user changing this again, so we don't expose beyond init
        self.cores = cores
        self.region = region
        self.min_score = min_score
        self.linprog_method = linprog_method
        self.randomize_by = randomize_by
        self.df = spot_cli.select_instances(
            data_file,
            bare_metal=bare_metal,
            hypervisor=hypervisor,
            has_gpu=has_gpu,
            arch=arch,
        )

        # Calculate all values we need on setup. Again, we assume that the optimizer is
        # not allowed to change values mid-usage (without creating a new instance)
        self.setup()

        # Calculate max instances needed for cores wanted
        self.calculate_max_instances()

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
            self.bounds.append((0, self.max_instances[size]))

        # Save the original bounds for reset later
        self.original_bounds = copy.deepcopy(self.bounds)

    def calculate_max_instances(self):
        """
        We want to create a maximum quantity we should ask for each based on spot score
        we use the spot scores API to find a count that corresponds with our
        risk tolerance. The API returns max value 9 (very likely) to 1 (unlikely)
        """
        cli = Client(use_cache=True, clouds=["aws"])

        # Get new prices data for each cloud
        cloud = cli.get_clouds()[0]
        cloud._set_services()

        # Start with quota (only 50)
        have_quota = True

        # Create a maximum quantity we should ask for each based on spot score
        # we use the spot scores API to find a count that corresponds with our
        # risk tolerance. The API returns max value 9 (very likely) to 1 (unlikely)
        self.max_instances = {}
        for core, count in self.needed_counts.items():
            # We can only ask for a max estimate of 50
            if count > 50:
                count = 50

            if not have_quota:
                break

            # Just put this here for testing, or if we ever get a cache
            if core in self.max_instances:
                continue

            # Get instance types for this size
            instance_types = self.df[self.df.cores == core].instance.tolist()

            # Step 1: Calculate the max number of instances we might choose for the type
            while have_quota and count > 0:
                print(f"Getting spot score for instances of size {core}")
                try:
                    score = cloud.ec2_client.get_spot_placement_scores(
                        InstanceTypes=instance_types,
                        RegionNames=[self.region],
                        TargetCapacity=count,
                        TargetCapacityUnitType="units",
                    )
                except Exception as e:
                    print(f"Hit an error: {e}, likely out of quota")
                    have_quota = False
                    break

                # If the score is == our risk tolerance, we are good!
                score = score["SpotPlacementScores"][0]["Score"]

                # If we are in the risk tolerance, break from the while
                if score >= self.min_score:
                    print(
                        f"✅️ Spot score: size {core}     [satisfed]: {count} instances (score: {score})"
                    )
                    self.max_instances[core] = count
                    break

                # We don't have a lot of queries, so decrease by 1/3
                # if score < args.min_score:
                # Take the maximum of 1 and current minus 1/3
                print(
                    f"❌️ Spot score: size {core} [not-satisfed]: {count} instances (score: {score})"
                )
                count = max(1, count - math.ceil(1 / 3 * count))

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

        # We will use order of sizes to calculate bounds (from spot score api)
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
        bare_metal=args.bare_metal,
        hypervisor=args.hypervisor,
        has_gpu=args.has_gpu,
        arch=args.arch,
        region=args.region,
        min_score=args.min_score,
        linprog_method=args.linprog_method,
        randomize_by=args.randomize,
    )

    # Run the initial algorithm! This gives us a first result to start from
    result = poo.run()

    # Save json dict of results
    results = []

    # Keep track of results we have seen
    seen = set()

    # The top result is always added, we haven't seen it yet!
    print(result)
    print("\n⭐️ Suggested top request (accounting for price and spot scores):")
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
