# generate_timetable.py
#
# Reads classes.json (subjects each class can be taught), teachers.json
# (subjects each teacher can teach), rooms.json, periods.json (the time for
# each period number) and days.json (which periods run on which day - e.g.
# Wednesday is a half day) then uses Z3 to build ONE valid timetable for the
# whole week: for every day/period slot, every class is taught one of its
# subjects, by a teacher qualified for that subject, in a room - with no
# teacher or room double-booked in the same day/period slot.
#
# This is a "does a working timetable exist" solve, not an optimal one:
# there's no attempt to vary subjects across slots, balance teacher load,
# or avoid repeats. It just proves (and produces) a feasible schedule.

import json
import os

from z3 import *


def load_json(folder, name):
    with open(os.path.join(folder, name)) as f:
        return json.load(f)


def build_timetable(classes, teachers, rooms, periods, days):
    class_names = list(classes.keys())
    teacher_names = list(teachers.keys())
    subjects = sorted({s for subs in classes.values() for s in subs})

    subject_index = {s: i for i, s in enumerate(subjects)}
    teacher_index = {t: i for i, t in enumerate(teacher_names)}

    # every (day, period) slot that actually exists this week
    slots = [(day, str(period)) for day, day_periods in days.items() for period in day_periods]

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

    subject_vars = {}
    teacher_vars = {}
    room_vars = {}

    s = Solver()

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

        # no teacher or room can be double-booked within the same slot
        s.add(Distinct([teacher_vars[(c, day, period)] for c in class_names]))
        s.add(Distinct([room_vars[(c, day, period)] for c in class_names]))

    if s.check() != sat:
        return None

    model = s.model()
    timetable = {day: {} for day in days}
    for day, period in slots:
        timetable[day][period] = {}
        for class_name in class_names:
            subject_idx = model[subject_vars[(class_name, day, period)]].as_long()
            teacher_idx = model[teacher_vars[(class_name, day, period)]].as_long()
            room_idx = model[room_vars[(class_name, day, period)]].as_long()
            timetable[day][period][class_name] = {
                "subject": subjects[subject_idx],
                "teacher": teacher_names[teacher_idx],
                "room": rooms[room_idx],
            }

    return timetable


def period_time(periods, period):
    return f"{periods[period]['start_time']}-{periods[period]['end_time']}"


def safe_filename(name):
    return name.replace(" ", "_") + ".md"


def write_markdown_grid(path, title, days, periods, cell_text):
    day_names = list(days.keys())
    period_names = sorted(periods.keys(), key=int)

    lines = [f"# {title}", ""]
    lines.append("| Period | Time | " + " | ".join(day_names) + " |")
    lines.append("|--------|------|" + "|".join(["------"] * len(day_names)) + "|")

    for period in period_names:
        row = [period, period_time(periods, period)]
        for day in day_names:
            if period not in [str(p) for p in days[day]]:
                row.append("-")
            else:
                row.append(cell_text(day, period) or "*Free*")
        lines.append("| " + " | ".join(row) + " |")

    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def write_class_timetables(folder, timetable, periods, days, classes):
    class_dir = os.path.join(folder, "classes")
    os.makedirs(class_dir, exist_ok=True)

    for class_name in classes:
        def cell_text(day, period, class_name=class_name):
            info = timetable[day][period][class_name]
            return f"{info['subject']}<br>{info['teacher']}<br>{info['room']}"

        write_markdown_grid(
            os.path.join(class_dir, safe_filename(class_name)),
            f"Timetable for {class_name}",
            days,
            periods,
            cell_text,
        )


def write_teacher_timetables(folder, timetable, periods, days, teachers):
    teacher_dir = os.path.join(folder, "teachers")
    os.makedirs(teacher_dir, exist_ok=True)

    schedule = {teacher_name: {} for teacher_name in teachers}
    for day, day_periods in timetable.items():
        for period, entries in day_periods.items():
            for class_name, info in entries.items():
                schedule[info["teacher"]][(day, period)] = f"{class_name}<br>{info['subject']}<br>{info['room']}"

    for teacher_name in teachers:
        write_markdown_grid(
            os.path.join(teacher_dir, safe_filename(teacher_name)),
            f"Timetable for {teacher_name}",
            days,
            periods,
            lambda day, period, teacher_name=teacher_name: schedule[teacher_name].get((day, period)),
        )


def write_room_timetables(folder, timetable, periods, days, rooms):
    room_dir = os.path.join(folder, "rooms")
    os.makedirs(room_dir, exist_ok=True)

    schedule = {room_name: {} for room_name in rooms}
    for day, day_periods in timetable.items():
        for period, entries in day_periods.items():
            for class_name, info in entries.items():
                schedule[info["room"]][(day, period)] = f"{class_name}<br>{info['subject']}<br>{info['teacher']}"

    for room_name in rooms:
        write_markdown_grid(
            os.path.join(room_dir, safe_filename(room_name)),
            f"Timetable for {room_name}",
            days,
            periods,
            lambda day, period, room_name=room_name: schedule[room_name].get((day, period)),
        )


def main():
    folder = os.path.dirname(os.path.abspath(__file__))

    classes = load_json(folder, "classes.json")
    teachers = load_json(folder, "teachers.json")
    rooms = load_json(folder, "rooms.json")
    periods = load_json(folder, "periods.json")
    days = load_json(folder, "days.json")

    timetable = build_timetable(classes, teachers, rooms, periods, days)

    if timetable is None:
        print("No valid timetable found.")
        return

    output_path = os.path.join(folder, "timetable.json")
    with open(output_path, "w") as f:
        json.dump(timetable, f, indent=4)

    write_class_timetables(folder, timetable, periods, days, classes)
    write_teacher_timetables(folder, timetable, periods, days, teachers)
    write_room_timetables(folder, timetable, periods, days, rooms)

    total_slots = sum(len(p) for p in days.values())
    print(f"Generated a valid weekly timetable for {len(classes)} classes across {total_slots} day/period slots.")
    print(f"Saved to {output_path}")
    print("Wrote per-class, per-teacher and per-room markdown timetables to classes/, teachers/ and rooms/")


if __name__ == "__main__":
    main()
