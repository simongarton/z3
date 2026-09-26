# generate_max_time_combinations.py
#
# Reads a course data file (list of courses, each with an id, name, and a
# schedule of time slots) and uses Z3 to find the conflict-free combination
# of courses that maximises total time spent in class. If more than one
# combination ties for the maximum, all of them are returned.
#
# Step 1: use Optimize to find the maximum possible total hours, subject to
# no two chosen courses sharing a schedule slot.
# Step 2: switch to a plain Solver with that maximum pinned as a constraint,
# and enumerate every combination that achieves it via blocking clauses.

import argparse
import json
import os

from z3 import *


def load_courses(path):
    with open(path) as f:
        return json.load(f)


def find_conflicts(courses):
    conflicts = []
    for i in range(len(courses)):
        for j in range(i + 1, len(courses)):
            shared = set(courses[i]["schedule"]) & set(courses[j]["schedule"])
            if shared:
                conflicts.append((i, j))
    return conflicts


def slot_hours(slot):
    # slot looks like "Monday 9:00-10:00" - assumes same-day, whole-hour slots
    _, times = slot.split(" ", 1)
    start, end = times.split("-")
    start_hour = int(start.split(":")[0])
    end_hour = int(end.split(":")[0])
    diff = end_hour - start_hour
    if diff <= 0:
        diff += 12
    return diff


def course_hours(course):
    return sum(slot_hours(slot) for slot in course["schedule"])


def find_max_time_combinations(courses):
    conflicts = find_conflicts(courses)
    durations = [course_hours(c) for c in courses]
    course_vars = [Bool(f"course_{c['id']}") for c in courses]

    def base_constraints(solver):
        for i, j in conflicts:
            solver.add(Not(And(course_vars[i], course_vars[j])))
        solver.add(Or(course_vars))

    total_time = Sum(
        [If(var, durations[i], 0) for i, var in enumerate(course_vars)]
    )

    o = Optimize()
    base_constraints(o)
    o.maximize(total_time)

    if o.check() != sat:
        return [], 0

    max_time = o.model().eval(total_time).as_long()

    s = Solver()
    base_constraints(s)
    s.add(total_time == max_time)

    combinations = []
    while s.check() == sat:
        model = s.model()
        selected = [
            courses[i]["name"]
            for i, var in enumerate(course_vars)
            if is_true(model[var])
        ]
        combinations.append(selected)

        block = Or(
            [Not(var) if is_true(model[var]) else var for var in course_vars]
        )
        s.add(block)

    return combinations, max_time


def main():
    parser = argparse.ArgumentParser(
        description="Find the conflict-free course combination(s) that maximise time in class, using Z3."
    )
    parser.add_argument(
        "input",
        nargs="?",
        default="course_data_10.json",
        help="Course data JSON file (in the same folder as this script). Default: course_data_10.json",
    )
    args = parser.parse_args()

    folder = os.path.dirname(os.path.abspath(__file__))
    input_path = os.path.join(folder, args.input)

    courses = load_courses(input_path)
    combinations, max_time = find_max_time_combinations(courses)

    base, _ = os.path.splitext(os.path.basename(input_path))
    output_name = base.replace("course_data", "course_max_time") + ".json"
    output_path = os.path.join(folder, output_name)

    with open(output_path, "w") as f:
        json.dump(
            {"max_hours_in_class": max_time, "combinations": combinations},
            f,
            indent=4,
        )

    print(f"Maximum time in class: {max_time} hours")
    print(f"Found {len(combinations)} combination(s) achieving that maximum.")
    print(f"Saved to {output_path}")


if __name__ == "__main__":
    main()
