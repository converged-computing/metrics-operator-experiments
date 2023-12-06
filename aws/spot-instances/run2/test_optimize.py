#!/usr/bin/env python3

# Testing using scipy.minimize
# pip install scipy

import argparse
import os
import sys
import math
import scipy.optimize
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

    # Be generous with initial selection, select specific hypervisor and not bare metal
    df = spot_cli.select_instances(
        data_file,
        bare_metal=args.bare_metal,
        hypervisor=args.hypervisor,
        has_gpu=args.has_gpu,
        arch=args.arch,
    )

    # Calculate the price / cores
    df["price_per_core"] = df.spot_price / df.cores
    # This was just for my viewing
    # sorted_df = df.sort_values(["price_per_core", "cores"])

    # Unique quantities of cores, and mean cost by size
    unique_cores = df.cores.unique().tolist()
    mean_costs_per_core = {}
    mean_costs = {}

    # Let's keep track of the number available for each.
    # We don't generally want to trust a size with less than 4.
    available = {}

    # We also will calculate the min number of instances needed for each type
    needed_counts = {}

    # Get mean value for each (to minimize)
    # The second was just for my FYI, for example when we don't set bounds,
    # the optimizer chooses 4 x 128, which has the cheapest cost / core
    for core in unique_cores:
        mean_costs[core] = df[df.cores == core].spot_price.mean()
        mean_costs_per_core[core] = df[df.cores == core].price_per_core.mean()
        available[core] = df[df.cores == core].shape[0]
        # Take a ceiling, having a little extra is OK
        needed_counts[core] = math.ceil(args.cores / core)

    # We will use order of sizes to calculate bounds (from spot score api)
    sizes = list(mean_costs.keys())
    cli = Client(use_cache=True, clouds=["aws"])

    # Get new prices data for each cloud
    cloud = cli.get_clouds()[0]
    cloud._set_services()

    # Start with quota (only 50)
    have_quota = True

    # Create a maximum quantity we should ask for each based on spot score
    # we use the spot scores API to find a count that corresponds with our
    # risk tolerance. The API returns max value 9 (very likely) to 1 (unlikely)
    max_instances = {}
    for core, count in needed_counts.items():
        # We can only ask for a max estimate of 50
        if count > 50:
            count = 50

        if not have_quota:
            break

        # Just put this here for testing, or if we ever get a cache
        if core in max_instances:
            continue

        # Get instance types for this size
        instance_types = df[df.cores == core].instance.tolist()

        # Step 1: Calculate the max number of instances we might choose for the type
        while have_quota and count > 0:
            print(f"Getting spot score for instances of size {core}")
            try:
                score = cloud.ec2_client.get_spot_placement_scores(
                    InstanceTypes=instance_types,
                    RegionNames=[args.region],
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
            if score >= args.min_score:
                print(
                    f"✅️ Spot score: size {core}     [satisfed]: {count} instances (score: {score})"
                )
                max_instances[core] = count
                break

            # We don't have a lot of queries, so decrease by 1/3
            # But take
            # if score < args.min_score:
            # Take the maximum of 1 and current minus 1/3
            print(
                f"❌️ Spot score: size {core} [not-satisfed]: {count} instances (score: {score})"
            )
            count = max(1, count - math.ceil(1 / 3 * count))

    # Now assemble a min (0) and max instances for each size!
    # Note that this goes only up to the size we generated above.
    # We could fudge a little bit.
    bounds = []
    for size in sizes:
        bounds.append((0, max_instances[size]))

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
    costs = list(mean_costs.values())

    # Let's set A_ub to a numpy array
    # First row is all ones, this just counts the instances
    A1 = len(costs) * [1]
    # second row is negative of the number of cores per instance
    # it has to be negative because inequality has to be flipped
    A2 = [x * -1 for x in sizes]
    A = [A1, A2]

    # b_ub is a 1-D array with just two values:
    # the maximum number of instances (the same as the cores, if we select sizes of 1)
    # and NEGATIVE the minimum number of cores (again, inequality is flipped)
    b_ub = [args.cores, -1 * args.cores]

    # The function assumes less than or equal to, but for cores we want greater or equal to
    # If we want to set an upper bound on cores we would have a third row
    # This would say "Must be 0 or greater (all of them)"
    # bounds = (0, None)
    # But I think we want to bound based on selection of instance types available.

    # Must be integer values
    integrality = 1

    # Try it out?
    # Note that we can set a callback to print steps
    result = scipy.optimize.linprog(
        costs,
        A_ub=A,
        b_ub=b_ub,
        bounds=bounds,
        integrality=integrality,
        method=args.linprog_method,
    )

    # Save json dict of results
    results = []

    # Keep track of results we have seen
    seen = set()

    print(result)
    print("\n⭐️ Suggested top request (accounting for price and spot scores):")
    for i, count in enumerate(result.x):
        res = show_result(result, sizes, mean_costs, available)
        if res and res["uid"] not in seen:
            seen.add(res["uid"])
            del res["uid"]
            print_result(res)
            results.append(res)

    print("\nCalculating remainder of results (total {args.results})")
    args.results -= 1

    # Find the first non-zero, and decrease by one in the bounds
    while args.results > 0:
        for i, count in enumerate(result.x):
            if count != 0:
                bound = bounds[i]

                # We can't go any lower, we've eliminated this
                if bound[1] <= 0:
                    continue

                # If we get here, decrease the bound by 1
                bounds[i] = (bound[0], bound[1] - 1)

                # Calculate the new result (with new bounds)
                # It might have different sets of instances
                result = scipy.optimize.linprog(
                    costs,
                    A_ub=A,
                    b_ub=b_ub,
                    bounds=bounds,
                    integrality=integrality,
                    method=args.linprog_method,
                )
                res = show_result(result, sizes, mean_costs, available)
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


def show_result(result, sizes, mean_costs, available):
    """
    Given a count, size, and mean costs,
    print the nice result for the user!
    """
    # One result might have multiple instances
    single_result = {"instances": []}
    total_cost = 0
    total_count = 0

    # Create a unique id so we know if we've seen it before
    uid = ""
    for i, count in enumerate(result.x):
        size = sizes[i]

        # IMPORTANT: the result looks like an int, but is a long float
        # This might introduce error, look at again at some point
        count = int(round(count))
        if count != 0:
            if uid:
                uid += f"-{size}-{count}"
            else:
                uid = f"{size}-{count}"

            # Cost for this set of instances
            cost_per_instance = round(mean_costs[size], 2)
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
                    "available": available[size],
                }
            )

    single_result["uid"] = uid
    single_result["total_count"] = total_count
    single_result["total_cost"] = total_cost
    total_cost = round(total_cost, 2)
    return single_result


if __name__ == "__main__":
    main()
