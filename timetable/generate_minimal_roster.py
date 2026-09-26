# generate_minimal_roster.py
#
# A different question to the rest of timetable/: not "when does everyone
# teach", but "who do we actually need on staff at all". If teachers never
# need a break and can teach every session (so one Chemistry teacher can
# cover every class's Chemistry needs at once, with no scheduling conflict
# possible), the only thing that matters is subject coverage: every subject
# that some class needs has to be taught by at least one retained teacher.
# That's a minimum set cover problem - minimise the number of teachers kept,
# from the existing qualified pool in teachers.json, such that every subject
# in classes.json is still covered by someone.
#
# Solved with Z3: minimise the count first with Optimize, then switch to a
# plain Solver pinned at that minimum and enumerate every tied solution via
# blocking clauses (same "find one, forbid it, repeat" pattern used for
# course combinations).

import json
import os

from z3 import *


def load_json(folder, name):
    with open(os.path.join(folder, name)) as f:
        return json.load(f)


def find_minimal_rosters(classes, teachers):
    subjects_needed = sorted({s for subs in classes.values() for s in subs})
    teacher_names = list(teachers.keys())
    teacher_vars = {name: Bool(name) for name in teacher_names}

    def base_constraints(s):
        for subject in subjects_needed:
            qualified = [teacher_vars[name] for name, subs in teachers.items() if subject in subs]
            s.add(Or(qualified))

    team_size = Sum([If(teacher_vars[name], 1, 0) for name in teacher_names])

    o = Optimize()
    base_constraints(o)
    o.minimize(team_size)
    if o.check() != sat:
        return None, []

    minimal_size = o.model().eval(team_size).as_long()

    s = Solver()
    base_constraints(s)
    s.add(team_size == minimal_size)

    rosters = []
    while s.check() == sat:
        model = s.model()
        selected = [name for name in teacher_names if is_true(model[teacher_vars[name]])]
        rosters.append(selected)
        block = Or([Not(teacher_vars[name]) if is_true(model[teacher_vars[name]]) else teacher_vars[name] for name in teacher_names])
        s.add(block)

    return minimal_size, rosters


def main():
    folder = os.path.dirname(os.path.abspath(__file__))
    classes = load_json(folder, "classes.json")
    teachers = load_json(folder, "teachers.json")

    subjects_needed = sorted({s for subs in classes.values() for s in subs})
    minimal_size, rosters = find_minimal_rosters(classes, teachers)

    print(f"{len(subjects_needed)} subjects need covering: {', '.join(subjects_needed)}")
    print(f"Minimum roster size: {minimal_size} (out of {len(teachers)} teachers currently on staff)")
    print(f"Found {len(rosters)} different roster(s) achieving that minimum:\n")

    output = {"subjects_needed": subjects_needed, "minimal_size": minimal_size, "rosters": []}

    for i, roster in enumerate(rosters, 1):
        print(f"Roster {i}: {', '.join(roster)}")
        roster_detail = {name: teachers[name] for name in roster}
        for name in roster:
            print(f"  {name}: {', '.join(teachers[name])}")
        output["rosters"].append(roster_detail)
        print()

    output_path = os.path.join(folder, "minimal_roster.json")
    with open(output_path, "w") as f:
        json.dump(output, f, indent=4)
    print(f"Saved to {output_path}")


if __name__ == "__main__":
    main()
