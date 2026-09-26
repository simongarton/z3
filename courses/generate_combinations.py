# generate_combinations.py
#
# Reads a course data file (list of courses, each with an id, name, and a
# schedule of time slots) and uses Z3 to enumerate every combination of
# courses that has no schedule conflicts, i.e. no two chosen courses ever
# share the same day/time slot.
#
# Each satisfying combination is found by asking Z3 for a model, recording
# it, then adding a "blocking clause" that rules that exact combination out
# so the next o.check() finds a different one. Repeating this until the
# solver reports unsat enumerates all valid combinations.

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


def generate_combinations(courses):
    conflicts = find_conflicts(courses)

    course_vars = [Bool(f"course_{c['id']}") for c in courses]

    s = Solver()
    for i, j in conflicts:
        s.add(Not(And(course_vars[i], course_vars[j])))

    # disallow the empty schedule
    s.add(Or(course_vars))

    combinations = []
    while s.check() == sat:
        model = s.model()
        selected = [
            courses[i]["name"]
            for i, var in enumerate(course_vars)
            if is_true(model[var])
        ]
        combinations.append(selected)

        # block this exact combination so the next check() finds a new one
        block = Or(
            [
                Not(var) if is_true(model[var]) else var
                for var in course_vars
            ]
        )
        s.add(block)

    return combinations


def main():
    parser = argparse.ArgumentParser(
        description="Generate all conflict-free combinations of courses using Z3."
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
    combinations = generate_combinations(courses)

    base, _ = os.path.splitext(os.path.basename(input_path))
    output_name = base.replace("course_data", "course_combinations") + ".json"
    output_path = os.path.join(folder, output_name)

    with open(output_path, "w") as f:
        json.dump(combinations, f, indent=4)

    print(f"Found {len(combinations)} conflict-free combinations of {len(courses)} courses.")
    print(f"Saved to {output_path}")


if __name__ == "__main__":
    main()
