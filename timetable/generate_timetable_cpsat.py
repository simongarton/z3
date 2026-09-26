# generate_timetable_cpsat.py
#
# A from-scratch reimplementation of generate_timetable.py's "does a valid
# timetable exist" solve, using Google OR-Tools' CP-SAT instead of Z3 - to
# see how the two compare on the exact same problem. Deliberately has no
# dependency on the z3-based modules, so it's a fair standalone comparison.
#
# Same data, same rules: for every day/period slot, every class is taught
# one of its subjects, by a teacher qualified for that subject, in a room
# that supports it - with no teacher or room double-booked in the same
# slot. Also includes an optional teacher-load floor/cap experiment, since
# that hard cardinality constraint was the thing Z3 struggled with most.

import json
import os
import time

from ortools.sat.python import cp_model


def load_json(folder, name):
    with open(os.path.join(folder, name)) as f:
        return json.load(f)


def all_slots(days):
    return [(day, str(period)) for day, day_periods in days.items() for period in day_periods]


def build_model(classes, teachers, rooms, periods, days, subject_rooms):
    class_names = list(classes.keys())
    teacher_names = list(teachers.keys())
    subjects = sorted({s for subs in classes.values() for s in subs})

    subject_index = {s: i for i, s in enumerate(subjects)}
    teacher_index = {t: i for i, t in enumerate(teacher_names)}
    room_index = {r: i for i, r in enumerate(rooms)}

    slots = all_slots(days)

    # for each class, the valid (subject, teacher, room) triples: the
    # subject has to be one it takes, the teacher qualified for it, and the
    # room has to support it (or the subject has no room restriction at all)
    valid_triples = {}
    for class_name, class_subjects in classes.items():
        triples = []
        for subject in class_subjects:
            s_idx = subject_index[subject]
            allowed_rooms = subject_rooms.get(subject) or list(rooms)
            for teacher_name, teacher_subjects in teachers.items():
                if subject not in teacher_subjects:
                    continue
                t_idx = teacher_index[teacher_name]
                for room_name in allowed_rooms:
                    triples.append((s_idx, t_idx, room_index[room_name]))
        valid_triples[class_name] = triples

    model = cp_model.CpModel()

    subject_vars = {}
    teacher_vars = {}
    room_vars = {}

    for day, period in slots:
        for class_name in class_names:
            subject_var = model.NewIntVar(0, len(subjects) - 1, f"subject_{class_name}_{day}_{period}")
            teacher_var = model.NewIntVar(0, len(teacher_names) - 1, f"teacher_{class_name}_{day}_{period}")
            room_var = model.NewIntVar(0, len(rooms) - 1, f"room_{class_name}_{day}_{period}")

            subject_vars[(class_name, day, period)] = subject_var
            teacher_vars[(class_name, day, period)] = teacher_var
            room_vars[(class_name, day, period)] = room_var

            # a single table constraint replaces Z3's Or(And(...)) - CP-SAT
            # is built to reason over exactly this "allowed tuples" shape
            model.AddAllowedAssignments([subject_var, teacher_var, room_var], valid_triples[class_name])

        # no teacher or room can be double-booked within the same slot
        model.AddAllDifferent([teacher_vars[(c, day, period)] for c in class_names])
        model.AddAllDifferent([room_vars[(c, day, period)] for c in class_names])

    ctx = {
        "classes": classes,
        "class_names": class_names,
        "teacher_names": teacher_names,
        "subjects": subjects,
        "subject_index": subject_index,
        "subject_vars": subject_vars,
        "teacher_vars": teacher_vars,
        "room_vars": room_vars,
    }
    return model, ctx


def extract_timetable(solver, ctx, rooms, days):
    class_names = ctx["class_names"]
    teacher_names = ctx["teacher_names"]
    subjects = ctx["subjects"]

    timetable = {day: {} for day in days}
    for day, period in all_slots(days):
        timetable[day][period] = {}
        for class_name in class_names:
            subject_idx = solver.Value(ctx["subject_vars"][(class_name, day, period)])
            teacher_idx = solver.Value(ctx["teacher_vars"][(class_name, day, period)])
            room_idx = solver.Value(ctx["room_vars"][(class_name, day, period)])
            timetable[day][period][class_name] = {
                "subject": subjects[subject_idx],
                "teacher": teacher_names[teacher_idx],
                "room": rooms[room_idx],
            }
    return timetable


def add_teacher_load_bound(model, ctx, days, teacher_names, min_load=None, max_load=None):
    """Same fairness idea as the Z3 version's floor: bound how many lessons
    each teacher gets across the whole week. CP-SAT needs reified booleans
    (teacher_var == idx -> bool) to build a count, same shape as the Z3
    version's Sum(If(...)), but expressed with CP-SAT's native reification
    and linear constraint APIs."""

    class_names = ctx["class_names"]
    teacher_vars = ctx["teacher_vars"]
    slots = all_slots(days)

    for teacher_idx, _ in enumerate(teacher_names):
        indicators = []
        for day, period in slots:
            for c in class_names:
                b = model.NewBoolVar(f"is_{teacher_idx}_{c}_{day}_{period}")
                model.Add(teacher_vars[(c, day, period)] == teacher_idx).OnlyEnforceIf(b)
                model.Add(teacher_vars[(c, day, period)] != teacher_idx).OnlyEnforceIf(b.Not())
                indicators.append(b)
        total = sum(indicators)
        if min_load is not None:
            model.Add(total >= min_load)
        if max_load is not None:
            model.Add(total <= max_load)


def main():
    folder = os.path.dirname(os.path.abspath(__file__))

    classes = load_json(folder, "classes.json")
    teachers = load_json(folder, "teachers.json")
    rooms = load_json(folder, "rooms.json")
    periods = load_json(folder, "periods.json")
    days = load_json(folder, "days.json")
    subject_rooms = load_json(folder, "subjects.json")

    model, ctx = build_model(classes, teachers, rooms, periods, days, subject_rooms)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 60
    solver.parameters.num_search_workers = 8

    t0 = time.time()
    status = solver.Solve(model)
    elapsed = time.time() - t0

    print(f"Status: {solver.StatusName(status)} in {elapsed:.2f}s")

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        print("No valid timetable found.")
        return

    timetable = extract_timetable(solver, ctx, rooms, days)

    output_path = os.path.join(folder, "timetable_cpsat.json")
    with open(output_path, "w") as f:
        json.dump(timetable, f, indent=4)

    total_slots = sum(len(p) for p in days.values())
    print(f"Generated a valid weekly timetable for {len(classes)} classes across {total_slots} day/period slots.")
    print(f"Saved to {output_path}")


if __name__ == "__main__":
    main()
