# generate_subjects.py
#
# Creates subjects.json: keyed by subject name, with an empty list for each -
# a template for you to fill in by hand with the rooms that support that
# subject (e.g. a science lab for Science). Once filled in, this can be
# used as an extra hard constraint: a class can only be taught a subject in
# a room that supports it. An empty list for a subject means "no
# restriction recorded yet", not "no room supports it".

import json
import os

from generate_timetable import load_json


def main():
    folder = os.path.dirname(os.path.abspath(__file__))
    classes = load_json(folder, "classes.json")

    subjects = sorted({s for subs in classes.values() for s in subs})
    subject_rooms = {subject: [] for subject in subjects}

    output_path = os.path.join(folder, "subjects.json")
    with open(output_path, "w") as f:
        json.dump(subject_rooms, f, indent=4)

    print(f"Generated a subjects.json template for {len(subjects)} subjects.")
    print(f"Saved to {output_path}")


if __name__ == "__main__":
    main()
