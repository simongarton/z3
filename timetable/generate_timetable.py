# generate_timetable.py
#
# Reads classes.json (subjects each class can be taught), teachers.json
# (subjects each teacher can teach), rooms.json, periods.json (the time for
# each period number), days.json (which periods run on which day - e.g.
# Wednesday is a half day) and subjects.json (which rooms support each
# subject - an empty list means no restriction) then uses Z3 to build ONE
# valid timetable for the whole week: for every day/period slot, every class
# is taught one of its subjects, by a teacher qualified for that subject, in
# a room that supports it - with no teacher or room double-booked in the
# same day/period slot.
#
# This is a "does a working timetable exist" solve, not an optimal one:
# there's no attempt to vary subjects across slots, balance teacher load,
# or avoid repeats. It just proves (and produces) a feasible schedule.

import json
import os

from z3 import *

from timetable_colors import build_color_maps
from timetable_render import write_entity_timetables


def load_json(folder, name):
    with open(os.path.join(folder, name)) as f:
        return json.load(f)


def all_slots(days):
    """Every (day, period) slot that actually exists this week, period as a string."""
    return [(day, str(period)) for day, day_periods in days.items() for period in day_periods]


def build_constraints(s, classes, teachers, rooms, periods, days, subject_rooms):
    """Add the hard rules (valid subject/teacher pairing, room support, no
    double-booking) to solver/optimizer `s`, and return the variables and
    lookups needed to read a model back out, or to build further (soft)
    constraints on top."""

    class_names = list(classes.keys())
    teacher_names = list(teachers.keys())
    subjects = sorted({s for subs in classes.values() for s in subs})

    subject_index = {s: i for i, s in enumerate(subjects)}
    teacher_index = {t: i for i, t in enumerate(teacher_names)}
    room_index = {r: i for i, r in enumerate(rooms)}

    slots = all_slots(days)

    # for each class, the (subject_index, teacher_index) pairs that are
    # actually valid for it: the subject must be one it takes, and the
    # teacher must be qualified to teach that subject
    valid_pairs = {}
    for class_name, class_subjects in classes.items():
        pairs = []
        for subject in class_subjects:
            s_idx = subject_index[subject]
            for teacher_name, teacher_subjects in teachers.items():
                if subject in teacher_subjects:
                    pairs.append((s_idx, teacher_index[teacher_name]))
        valid_pairs[class_name] = pairs

    # for each subject, the room indices it's restricted to - an empty (or
    # missing) list in subjects.json means no restriction recorded yet, so
    # any room is fine
    allowed_rooms_by_subject = {}
    for subject in subjects:
        room_names = subject_rooms.get(subject) or []
        if room_names:
            allowed_rooms_by_subject[subject_index[subject]] = [room_index[r] for r in room_names]

    subject_vars = {}
    teacher_vars = {}
    room_vars = {}

    for day, period in slots:
        for class_name in class_names:
            subject_var = Int(f"subject_{class_name}_{day}_{period}")
            teacher_var = Int(f"teacher_{class_name}_{day}_{period}")
            room_var = Int(f"room_{class_name}_{day}_{period}")

            subject_vars[(class_name, day, period)] = subject_var
            teacher_vars[(class_name, day, period)] = teacher_var
            room_vars[(class_name, day, period)] = room_var

            s.add(
                Or(
                    [
                        And(subject_var == s_idx, teacher_var == t_idx)
                        for s_idx, t_idx in valid_pairs[class_name]
                    ]
                )
            )
            s.add(room_var >= 0, room_var < len(rooms))

            for s_idx, room_indices in allowed_rooms_by_subject.items():
                s.add(Implies(subject_var == s_idx, Or([room_var == r_idx for r_idx in room_indices])))

        # no teacher or room can be double-booked within the same slot
        s.add(Distinct([teacher_vars[(c, day, period)] for c in class_names]))
        s.add(Distinct([room_vars[(c, day, period)] for c in class_names]))

    return {
        "classes": classes,
        "class_names": class_names,
        "teacher_names": teacher_names,
        "subjects": subjects,
        "teacher_index": teacher_index,
        "subject_index": subject_index,
        "subject_vars": subject_vars,
        "teacher_vars": teacher_vars,
        "room_vars": room_vars,
    }


def extract_timetable(model, ctx, rooms, days):
    class_names = ctx["class_names"]
    teacher_names = ctx["teacher_names"]
    subjects = ctx["subjects"]
    subject_vars = ctx["subject_vars"]
    teacher_vars = ctx["teacher_vars"]
    room_vars = ctx["room_vars"]

    timetable = {day: {} for day in days}
    for day, period in all_slots(days):
        timetable[day][period] = {}
        for class_name in class_names:
            # model_completion=True: on a timed-out Optimize, variables the
            # solver never had to pin down are otherwise left unassigned
            subject_idx = model.eval(subject_vars[(class_name, day, period)], model_completion=True).as_long()
            teacher_idx = model.eval(teacher_vars[(class_name, day, period)], model_completion=True).as_long()
            room_idx = model.eval(room_vars[(class_name, day, period)], model_completion=True).as_long()
            timetable[day][period][class_name] = {
                "subject": subjects[subject_idx],
                "teacher": teacher_names[teacher_idx],
                "room": rooms[room_idx],
            }
    return timetable


def add_teacher_load_floor(s, ctx, days, min_load):
    """Hard floor: every teacher must be booked for at least min_load lessons
    across the whole week, so nobody ends up nearly idle. This is a global
    (whole-week) constraint, so it only makes sense against a single solve
    that sees every slot at once - it is not used by the day-by-day
    optimizer, which never sees more than one day's slots at a time.

    A *minimum* was picked deliberately over a *maximum*: this is meant to
    stop a teacher like "only ever gets 7 lessons" happening, not to cap
    the busy ones. It also turned out to matter for solve time - capping
    every teacher's load (an upper bound) made Z3 time out even at a
    trivially-true bound, while a floor like this solves in ~10s. A floor
    only asks the solver to find enough slots for each teacher (existential,
    cheap); a cap asks it to prove none exist beyond a point across an
    already-huge, highly symmetric search space (expensive)."""

    class_names = ctx["class_names"]
    teacher_vars = ctx["teacher_vars"]

    for teacher_idx in range(len(ctx["teacher_names"])):
        total = Sum(
            [If(teacher_vars[(c, day, period)] == teacher_idx, 1, 0) for day, period in all_slots(days) for c in class_names]
        )
        s.add(total >= min_load)


def build_timetable(classes, teachers, rooms, periods, days, subject_rooms, min_teacher_load=None):
    s = Solver()
    ctx = build_constraints(s, classes, teachers, rooms, periods, days, subject_rooms)

    if min_teacher_load is not None:
        add_teacher_load_floor(s, ctx, days, min_teacher_load)

    if s.check() != sat:
        return None

    return extract_timetable(s.model(), ctx, rooms, days)


def write_all_timetables(folder, timetable, periods, days, classes, teachers, rooms, suffix=""):
    subjects = sorted({s for subs in classes.values() for s in subs})
    color_maps = build_color_maps(list(classes.keys()), list(teachers.keys()), rooms, subjects)

    write_entity_timetables(folder, timetable, periods, days, list(classes.keys()), "class", color_maps, f"classes{suffix}")
    write_entity_timetables(folder, timetable, periods, days, list(teachers.keys()), "teacher", color_maps, f"teachers{suffix}")
    write_entity_timetables(folder, timetable, periods, days, rooms, "room", color_maps, f"rooms{suffix}")


def compute_load(timetable, entity_kind, entity_names):
    """How many lessons each entity (teacher or room) is booked for across
    the whole week, including 0 for any that are never used."""
    load = {name: 0 for name in entity_names}
    for day_periods in timetable.values():
        for entries in day_periods.values():
            for info in entries.values():
                load[info[entity_kind]] += 1
    return load


def write_load_reports(folder, timetable, teachers, rooms, suffix=""):
    teacher_load = compute_load(timetable, "teacher", list(teachers.keys()))
    room_load = compute_load(timetable, "room", rooms)

    with open(os.path.join(folder, f"teacher_load{suffix}.json"), "w") as f:
        json.dump(teacher_load, f, indent=4)
    with open(os.path.join(folder, f"room_load{suffix}.json"), "w") as f:
        json.dump(room_load, f, indent=4)


# the minimum number of lessons/week every teacher must be given, so a
# narrowly-qualified teacher (like one who only teaches a rarely-picked
# subject) doesn't end up nearly idle. Empirically, 15 solves in ~10s;
# pushing this much higher (e.g. 20) made it too hard to solve at all.
MIN_TEACHER_LOAD = 15


def main():
    folder = os.path.dirname(os.path.abspath(__file__))

    classes = load_json(folder, "classes.json")
    teachers = load_json(folder, "teachers.json")
    rooms = load_json(folder, "rooms.json")
    periods = load_json(folder, "periods.json")
    days = load_json(folder, "days.json")
    subject_rooms = load_json(folder, "subjects.json")

    total_slots = sum(len(p) for p in days.values())

    timetable = build_timetable(classes, teachers, rooms, periods, days, subject_rooms, MIN_TEACHER_LOAD)

    if timetable is None:
        print("No valid timetable found.")
        return

    output_path = os.path.join(folder, "timetable.json")
    with open(output_path, "w") as f:
        json.dump(timetable, f, indent=4)

    write_all_timetables(folder, timetable, periods, days, classes, teachers, rooms)
    write_load_reports(folder, timetable, teachers, rooms)

    print(f"Generated a valid weekly timetable for {len(classes)} classes across {total_slots} day/period slots.")
    print(f"Every teacher guaranteed at least {MIN_TEACHER_LOAD} lessons/week.")
    print(f"Saved to {output_path}")
    print("Wrote per-class, per-teacher and per-room markdown + PNG timetables to classes/, teachers/ and rooms/")
    print("Wrote teacher_load.json and room_load.json")


if __name__ == "__main__":
    main()
