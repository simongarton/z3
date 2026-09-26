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
# Every current rule (optimisation_rules.py) only ever compares consecutive
# periods within the SAME day - none of them look across days. That means
# the whole week is really 5 independent optimization problems, not one big
# one, and solving it as 5 small problems instead of 1 huge one drastically
# shrinks the search space Z3 has to explore per solve, e.g. proving a day's
# schedule optimal outright rather than timing out on the whole week.
#
# With teachers/rooms often interchangeable within a slot, that search space
# is still symmetric, so *proving* an assignment optimal can take longer
# than finding a very good one even per day. So each day's search still
# uses its own bounded search with a plain Solver: solve, then require a
# strictly better score than that for this day, and repeat. Every accepted
# answer comes from an actual `sat` result, so it's always a fully valid
# timetable - we simply stop improving once time runs out, or once a
# request for something better comes back `unsat` (a proven optimum).

import json
import os
import time

from z3 import Solver, sat, unsat

from generate_timetable import build_constraints, extract_timetable, load_json, write_all_timetables, write_load_reports
from optimisation_rules import RULES

TIME_BUDGET_SECONDS_PER_DAY = 30


def load_rule_config(folder):
    catalogue = load_json(folder, "optimisation.json")
    run_config = load_json(folder, "optimisations.json")
    return catalogue, run_config


def active_rules(catalogue, run_config):
    """Rule ids that are both configured for this run and actually
    implemented, in run_config's order."""
    active = []
    for rule_id, weight in run_config.items():
        if rule_id not in catalogue:
            print(f"Warning: '{rule_id}' is in optimisations.json but not in optimisation.json - skipping.")
            continue
        if rule_id not in RULES:
            print(f"Warning: '{rule_id}' has no implementation in optimisation_rules.py yet - skipping.")
            continue
        active.append(rule_id)
    return active


def build_score(ctx, catalogue, run_config, rule_ids):
    """Return (total_objective, per_rule_terms) where per_rule_terms maps
    rule_id -> raw_term for every rule in rule_ids. total_objective is None
    if rule_ids is empty."""

    per_rule_terms = {}
    total = None

    for rule_id in rule_ids:
        raw_term = RULES[rule_id](ctx)
        per_rule_terms[rule_id] = raw_term

        weighted_term = run_config[rule_id] * raw_term
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


def solve_day(classes, teachers, rooms, periods, day, day_periods, subject_rooms, catalogue, run_config, rule_ids, time_budget_seconds):
    sub_days = {day: day_periods}

    s = Solver()
    ctx = build_constraints(s, classes, teachers, rooms, periods, sub_days, subject_rooms)
    ctx["days"] = sub_days

    total, per_rule_terms = build_score(ctx, catalogue, run_config, rule_ids)

    started = time.time()
    model, score, proven_optimal = search_for_best(s, total, time_budget_seconds)
    elapsed = time.time() - started

    if model is None:
        return None

    day_timetable = extract_timetable(model, ctx, rooms, sub_days)[day]
    counts = {rule_id: model.eval(term, model_completion=True).as_long() for rule_id, term in per_rule_terms.items()}

    return {
        "timetable": day_timetable,
        "score": score,
        "proven_optimal": proven_optimal,
        "elapsed": elapsed,
        "counts": counts,
    }


def main():
    folder = os.path.dirname(os.path.abspath(__file__))

    classes = load_json(folder, "classes.json")
    teachers = load_json(folder, "teachers.json")
    rooms = load_json(folder, "rooms.json")
    periods = load_json(folder, "periods.json")
    days = load_json(folder, "days.json")
    subject_rooms = load_json(folder, "subjects.json")

    catalogue, run_config = load_rule_config(folder)
    rule_ids = active_rules(catalogue, run_config)

    timetable = {}
    total_score = 0
    total_elapsed = 0.0
    all_proven = True
    aggregate_counts = {rule_id: 0 for rule_id in rule_ids}

    for day, day_periods in days.items():
        result = solve_day(classes, teachers, rooms, periods, day, day_periods, subject_rooms, catalogue, run_config, rule_ids, TIME_BUDGET_SECONDS_PER_DAY)

        if result is None:
            print(f"No valid timetable found for {day}.")
            return

        timetable[day] = result["timetable"]
        total_score += result["score"]
        total_elapsed += result["elapsed"]
        all_proven = all_proven and result["proven_optimal"]

        for rule_id, count in result["counts"].items():
            aggregate_counts[rule_id] += count

        status = "PROVEN OPTIMAL" if result["proven_optimal"] else "not proven optimal"
        print(f"  {day}: {status}, score {result['score']}, took {result['elapsed']:.1f}s")

    print()
    if all_proven:
        print(f"PROVEN OPTIMAL overall (score {total_score}) - every day solved to a confirmed optimum, total search time {total_elapsed:.1f}s.")
    else:
        print(
            f"NOT proven optimal overall - at least one day hit its {TIME_BUDGET_SECONDS_PER_DAY}s budget. "
            f"Best confirmed-valid combined score: {total_score} (total search time {total_elapsed:.1f}s)."
        )

    output_path = os.path.join(folder, "timetable_optimal.json")
    with open(output_path, "w") as f:
        json.dump(timetable, f, indent=4)

    write_all_timetables(folder, timetable, periods, days, classes, teachers, rooms, suffix="_optimal")
    write_load_reports(folder, timetable, teachers, rooms, suffix="_optimal")

    print("Score breakdown:")
    for rule_id in rule_ids:
        weight = run_config[rule_id]
        count = aggregate_counts[rule_id]
        print(f"  {rule_id} ({catalogue[rule_id]['plaintext']}): {count} x {weight} = {weight * count}")
    print(f"Total score: {total_score}")

    print(f"Saved to {output_path}")
    print("Wrote per-class, per-teacher and per-room markdown + PNG timetables to classes_optimal/, teachers_optimal/ and rooms_optimal/")
    print("Wrote teacher_load_optimal.json and room_load_optimal.json")


if __name__ == "__main__":
    main()
