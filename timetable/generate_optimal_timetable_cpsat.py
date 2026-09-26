# generate_optimal_timetable_cpsat.py
#
# The CP-SAT counterpart to generate_optimal_timetable.py - same problem,
# same rule catalogue (optimisation.json) and run configuration
# (optimisations.json), same weighted-sum scoring, but solved with Google
# OR-Tools' CP-SAT instead of Z3.
#
# The big structural difference from the Z3 version: no day-splitting, and
# no hand-rolled "solve, then demand strictly better, repeat" search loop.
# Both of those existed to work around specific Z3 weaknesses (an unsafe
# Optimize() timeout, and a search that couldn't shrink by splitting the
# week into days because the real bottleneck was per-slot symmetry, not
# problem size). CP-SAT's own Maximize() + time limit already reports a
# genuine, trustworthy status: OPTIMAL means proven best possible, FEASIBLE
# means "best found so far, with a computable gap to the true optimum" - so
# none of that workaround machinery is needed here.

import json
import os
import time

from ortools.sat.python import cp_model

from generate_timetable import write_all_timetables, write_load_reports
from generate_timetable_cpsat import build_model, extract_timetable, load_json
from optimisation_rules_cpsat import RULES

TIME_BUDGET_SECONDS = 60


def load_rule_config(folder):
    catalogue = load_json(folder, "optimisation.json")
    run_config = load_json(folder, "optimisations.json")
    return catalogue, run_config


def active_rules(catalogue, run_config):
    active = []
    for rule_id in run_config:
        if rule_id not in catalogue:
            print(f"Warning: '{rule_id}' is in optimisations.json but not in optimisation.json - skipping.")
            continue
        if rule_id not in RULES:
            print(f"Warning: '{rule_id}' has no CP-SAT implementation yet - skipping.")
            continue
        active.append(rule_id)
    return active


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

    model, ctx = build_model(classes, teachers, rooms, periods, days, subject_rooms)
    ctx["days"] = days
    ctx["num_rooms"] = len(rooms)

    raw_terms = {}
    objective_terms = []
    for rule_id in rule_ids:
        raw_term = RULES[rule_id](model, ctx)
        raw_terms[rule_id] = raw_term
        objective_terms.append(run_config[rule_id] * raw_term)

    if objective_terms:
        model.Maximize(sum(objective_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = TIME_BUDGET_SECONDS
    solver.parameters.num_search_workers = 8

    t0 = time.time()
    status = solver.Solve(model)
    elapsed = time.time() - t0

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        print(f"No valid timetable found ({solver.StatusName(status)}) after {elapsed:.1f}s.")
        return

    score = int(solver.ObjectiveValue()) if objective_terms else 0

    if status == cp_model.OPTIMAL:
        print(f"PROVEN OPTIMAL (score {score}) in {elapsed:.1f}s.")
    else:
        bound = solver.BestObjectiveBound()
        print(
            f"NOT proven optimal - best found within the {TIME_BUDGET_SECONDS}s budget "
            f"(took {elapsed:.1f}s): score {score}. Best possible is at most {bound:.0f} "
            f"(gap: {bound - score:.0f})."
        )

    timetable = extract_timetable(solver, ctx, rooms, days)

    output_path = os.path.join(folder, "timetable_cpsat_optimal.json")
    with open(output_path, "w") as f:
        json.dump(timetable, f, indent=4)

    write_all_timetables(folder, timetable, periods, days, classes, teachers, rooms, suffix="_cpsat_optimal")
    write_load_reports(folder, timetable, teachers, rooms, suffix="_cpsat_optimal")

    print("Score breakdown:")
    for rule_id in rule_ids:
        weight = run_config[rule_id]
        count = solver.Value(raw_terms[rule_id])
        print(f"  {rule_id} ({catalogue[rule_id]['plaintext']}): {count} x {weight} = {weight * count}")
    print(f"Total score: {score}")

    print(f"Saved to {output_path}")
    print("Wrote per-class, per-teacher and per-room markdown + PNG timetables to *_cpsat_optimal/")
    print("Wrote teacher_load_cpsat_optimal.json and room_load_cpsat_optimal.json")


if __name__ == "__main__":
    main()
