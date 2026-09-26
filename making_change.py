# making change
#
# This program calculates the minimum number of coins needed to make change for a given amount of money.
# I'm using Z3 to solve this problem.

import argparse

from z3 import *


def solve(amount, use_all):

    # available coins
    coins = [1, 5, 10, 25]

    coin_vars = [Int(f"coin_{i}") for i in range(len(coins))]

    o = Optimize()

    o.add(Sum([coin_vars[i] * coins[i] for i in range(len(coins))]) == amount)

    for var in coin_vars:
        o.add(var >= (1 if use_all else 0))

    # Minimize the total number of coins used
    o.minimize(Sum(coin_vars))

    if o.check() == sat:
        model = o.model()
        total_coins = sum(model[var].as_long() for var in coin_vars)
        print("Minimum number of coins needed:", total_coins)
        map = {}
        for i, var in enumerate(coin_vars):
            print(f"Number of {coins[i]}-cent coins:", model[var].as_long())
            map[coins[i]] = model[var].as_long()
        return total_coins, map
    else:
        print("No solution found.")
        return None, None


if __name__ == "__main__":
    argument_parser = argparse.ArgumentParser(
        description="Calculate the minimum number of coins needed to make change for a given amount of money."
    )
    argument_parser.add_argument(
        "amount", type=int, help="The amount of money to make change for."
    )
    argument_parser.add_argument(
        "use_all",
        type=lambda s: s.lower() in ("true", "1", "yes"),
        help="Whether to use all available coins.",
    )

    args = argument_parser.parse_args()

    solve(args.amount, args.use_all)
