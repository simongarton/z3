# making change dumb
#
# This program calculates the minimum number of coins needed to make change for a given amount of money.

import argparse

from z3 import *


def solve(amount):

    # available coins
    coins = [5, 10, 25]

    coin_vars = [Int(f"coin_{i}") for i in range(len(coins))]

    s = Solver()
    s.add(Sum([coin_vars[i] * coins[i] for i in range(len(coins))]) == amount)

    for var in coin_vars:
        s.add(var >= 0)

    if s.check() == sat:
        model = s.model()
        total_coins = sum(model[var].as_long() for var in coin_vars)
        print("Number of coins used:", total_coins)
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
        description="See if coins can be used to make change for a given amount of money."
    )
    argument_parser.add_argument(
        "amount", type=int, help="The amount of money to make change for."
    )

    args = argument_parser.parse_args()

    solve(args.amount)
