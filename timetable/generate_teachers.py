# generate_teachers.py
#
# Reads classes.json to find every subject taught across all classes, then
# generates TEACHER_COUNT teachers (named "Professor <Color>"), each able to
# teach between 1 and 3 subjects. Every subject is guaranteed at least one
# teacher, so the resulting teachers.json is always usable for scheduling.

import json
import os
import random

COLORS = [
    "Red", "Blue", "Green", "Yellow", "Purple", "Orange", "Black", "White",
    "Grey", "Pink", "Brown", "Cyan", "Magenta", "Violet", "Indigo", "Teal",
    "Maroon", "Navy", "Olive", "Gold",
]

TEACHER_COUNT = 12
MIN_SUBJECTS = 1
MAX_SUBJECTS = 3


def load_subjects(path):
    with open(path) as f:
        classes = json.load(f)
    subjects = set()
    for subject_list in classes.values():
        subjects.update(subject_list)
    return sorted(subjects)


def generate_teachers(subjects):
    names = [f"Professor {color}" for color in random.sample(COLORS, TEACHER_COUNT)]

    teachers = {
        name: random.sample(
            subjects, random.randint(MIN_SUBJECTS, min(MAX_SUBJECTS, len(subjects)))
        )
        for name in names
    }

    # guarantee every subject has at least one teacher who can teach it
    for subject in subjects:
        if any(subject in taught for taught in teachers.values()):
            continue
        name = random.choice(names)
        if len(teachers[name]) < MAX_SUBJECTS:
            teachers[name].append(subject)
        else:
            teachers[name][random.randrange(MAX_SUBJECTS)] = subject

    return teachers


def main():
    folder = os.path.dirname(os.path.abspath(__file__))
    subjects = load_subjects(os.path.join(folder, "classes.json"))
    teachers = generate_teachers(subjects)

    output_path = os.path.join(folder, "teachers.json")
    with open(output_path, "w") as f:
        json.dump(teachers, f, indent=4)

    print(f"Found {len(subjects)} subjects: {', '.join(subjects)}")
    print(f"Generated {len(teachers)} teachers.")
    print(f"Saved to {output_path}")


if __name__ == "__main__":
    main()
