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


def build_timetable(classes, teachers, rooms, periods, days, subject_rooms):
    s = Solver()
    ctx = build_constraints(s, classes, teachers, rooms, periods, days, subject_rooms)

    if s.check() != sat:
        return None

    return extract_timetable(s.model(), ctx, rooms, days)


def write_all_timetables(folder, timetable, periods, days, classes, teachers, rooms, suffix=""):
    subjects = sorted({s for subs in classes.values() for s in subs})
    color_maps = build_color_maps(list(classes.keys()), list(teachers.keys()), rooms, subjects)

    write_entity_timetables(folder, timetable, periods, days, list(classes.keys()), "class", color_maps, f"classes{suffix}")
    write_entity_timetables(folder, timetable, periods, days, list(teachers.keys()), "teacher", color_maps, f"teachers{suffix}")
    write_entity_timetables(folder, timetable, periods, days, rooms, "room", color_maps, f"rooms{suffix}")


def main():
    folder = os.path.dirname(os.path.abspath(__file__))

    classes = load_json(folder, "classes.json")
    teachers = load_json(folder, "teachers.json")
    rooms = load_json(folder, "rooms.json")
    periods = load_json(folder, "periods.json")
    days = load_json(folder, "days.json")
    subject_rooms = load_json(folder, "subjects.json")

    timetable = build_timetable(classes, teachers, rooms, periods, days, subject_rooms)

    if timetable is None:
        print("No valid timetable found.")
        return

    output_path = os.path.join(folder, "timetable.json")
    with open(output_path, "w") as f:
        json.dump(timetable, f, indent=4)

    write_all_timetables(folder, timetable, periods, days, classes, teachers, rooms)

    total_slots = sum(len(p) for p in days.values())
    print(f"Generated a valid weekly timetable for {len(classes)} classes across {total_slots} day/period slots.")
    print(f"Saved to {output_path}")
    print("Wrote per-class, per-teacher and per-room markdown + PNG timetables to classes/, teachers/ and rooms/")


if __name__ == "__main__":
    main()
