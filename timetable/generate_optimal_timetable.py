# generate_optimal_timetable.py
#
# Builds the same valid weekly timetable as generate_timetable.py, but
# searches for a better one according to a configurable, weighted set of
# soft rules, rather than settling for the first one Z3 finds.
#
# - timetable/optimisation.json is the catalogue of rules: an id, a
#   plaintext description of what's being optimised for, and a default
#   weight. New rules can be added here at any time; adding one here does
#   nothing on its own (see optimisation_rules.py).
# - timetable/optimisations.json is this run's configuration: which rule
#   ids to actually apply, and what weight/score to give each one. A rule
#   is entirely optional - if its id isn't in this file, it's simply not
#   used for this run, with no code changes needed.
#
# The score is the weighted sum, across every applied rule, of how many
# times that rule's pattern occurs in the timetable. Weights (and therefore
# the score) can be negative.
#
# With 15 largely-interchangeable teachers and rooms, the search space is
# hugely symmetric, so *proving* an assignment optimal can take far longer
# than finding a very good one. Z3's Optimize handles this internally with a
# timeout, but a model it hands back after timing out can leave some
# variables unassigned - and "completing" those independently can silently
# break joint constraints like Distinct (two classes ending up with the same
# teacher). So instead this does its own bounded search with a plain
# Solver: solve, then require a strictly better score than that, and repeat.
# Every accepted answer comes from an actual `sat` result, so it's always a
# fully valid timetable - we simply stop improving once time runs out, or
# once a request for something better comes back `unsat` (a proven optimum).

import json
import os
import time

from z3 import Solver, sat, unsat

from generate_timetable import build_constraints, extract_timetable, load_json, write_all_timetables
from optimisation_rules import RULES

TIME_BUDGET_SECONDS = 30


def load_rule_config(folder):
    catalogue = load_json(folder, "optimisation.json")
    run_config = load_json(folder, "optimisations.json")
    return catalogue, run_config


def build_score(ctx, catalogue, run_config):
    """Return (total_objective, per_rule_terms) where per_rule_terms maps
    rule_id -> (plaintext, weight, raw_term) for every rule actually applied
    this run. total_objective is None if no rules were applied."""

    per_rule_terms = {}
    total = None

    for rule_id, weight in run_config.items():
        if rule_id not in catalogue:
            print(f"Warning: '{rule_id}' is in optimisations.json but not in optimisation.json - skipping.")
            continue
        if rule_id not in RULES:
            print(f"Warning: '{rule_id}' has no implementation in optimisation_rules.py yet - skipping.")
            continue

        raw_term = RULES[rule_id](ctx)
        per_rule_terms[rule_id] = (catalogue[rule_id]["plaintext"], weight, raw_term)

        weighted_term = weight * raw_term
        total = weighted_term if total is None else total + weighted_term

    return total, per_rule_terms


def search_for_best(s, total, time_budget_seconds):
    """Repeatedly tighten the score requirement and re-solve, keeping only
    confirmed-valid (`sat`) models. Returns (best_model, best_score, proven_optimal)."""

    deadline = time.time() + time_budget_seconds

    def remaining_ms():
        return max(1, int((deadline - time.time()) * 1000))

    s.set("timeout", remaining_ms())
    if s.check() != sat:
        return None, None, False

    best_model = s.model()
    best_score = best_model.eval(total, model_completion=True).as_long() if total is not None else 0

    if total is None:
        return best_model, best_score, True

    while time.time() < deadline:
        s.add(total > best_score)
        s.set("timeout", remaining_ms())
        result = s.check()
        if result == sat:
            best_model = s.model()
            best_score = best_model.eval(total, model_completion=True).as_long()
        elif result == unsat:
            return best_model, best_score, True
        else:
            return best_model, best_score, False

    return best_model, best_score, False


def main():
    folder = os.path.dirname(os.path.abspath(__file__))

    classes = load_json(folder, "classes.json")
    teachers = load_json(folder, "teachers.json")
    rooms = load_json(folder, "rooms.json")
    periods = load_json(folder, "periods.json")
    days = load_json(folder, "days.json")

    catalogue, run_config = load_rule_config(folder)

    s = Solver()
    ctx = build_constraints(s, classes, teachers, rooms, periods, days)
    ctx["days"] = days

    total, per_rule_terms = build_score(ctx, catalogue, run_config)

    search_started = time.time()
    model, score, proven_optimal = search_for_best(s, total, TIME_BUDGET_SECONDS)
    elapsed = time.time() - search_started

    if model is None:
        print(f"No valid timetable found (after {elapsed:.1f}s).")
        return

    if proven_optimal:
        print(f"PROVEN OPTIMAL (score {score}) in {elapsed:.1f}s - Z3 confirmed no better score is possible.")
    else:
        print(
            f"NOT proven optimal - this is just the best confirmed-valid timetable found "
            f"within the {TIME_BUDGET_SECONDS}s search budget (took {elapsed:.1f}s): score {score}. "
            f"A better one may exist; increase TIME_BUDGET_SECONDS to search further."
        )

    timetable = extract_timetable(model, ctx, rooms, days)

    output_path = os.path.join(folder, "timetable_optimal.json")
    with open(output_path, "w") as f:
        json.dump(timetable, f, indent=4)

    write_all_timetables(folder, timetable, periods, days, classes, teachers, rooms, suffix="_optimal")

    print("Score breakdown:")
    grand_total = 0
    for rule_id, (plaintext, weight, raw_term) in per_rule_terms.items():
        count = model.eval(raw_term, model_completion=True).as_long()
        contribution = weight * count
        grand_total += contribution
        print(f"  {rule_id} ({plaintext}): {count} x {weight} = {contribution}")
    print(f"Total score: {grand_total}")

    print(f"Saved to {output_path}")
    print("Wrote per-class, per-teacher and per-room markdown + PNG timetables to classes_optimal/, teachers_optimal/ and rooms_optimal/")


if __name__ == "__main__":
    main()
