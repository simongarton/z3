# timetable_colors.py
#
# One consistent, pale colour per unique value of each of the four things
# that show up in a timetable cell: class, teacher, room, subject. Built
# once from the full known list of each, so a given value (e.g. "Room 101"
# or "Professor Pink") always gets the same colour everywhere it appears -
# whether that's on a class's diagram, a teacher's, or a room's.

import colorsys

LIGHTNESS = 0.85
SATURATION = 0.55


def pale_palette(values):
    ordered = sorted(values)
    n = len(ordered)
    palette = {}
    for i, value in enumerate(ordered):
        hue = i / n if n else 0
        r, g, b = colorsys.hls_to_rgb(hue, LIGHTNESS, SATURATION)
        palette[value] = (round(r * 255), round(g * 255), round(b * 255))
    return palette


def build_color_maps(class_names, teacher_names, rooms, subjects):
    return {
        "class": pale_palette(class_names),
        "teacher": pale_palette(teacher_names),
        "room": pale_palette(rooms),
        "subject": pale_palette(subjects),
    }
