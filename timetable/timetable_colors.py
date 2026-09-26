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

ACCENT_LIGHTNESS = 0.5
ACCENT_SATURATION = 0.75


def pale_palette(values):
    ordered = sorted(values)
    n = len(ordered)
    palette = {}
    for i, value in enumerate(ordered):
        hue = i / n if n else 0
        r, g, b = colorsys.hls_to_rgb(hue, LIGHTNESS, SATURATION)
        palette[value] = (round(r * 255), round(g * 255), round(b * 255))
    return palette


def accent_variant(color):
    """A more saturated, less pale version of a pale_palette() colour, for
    use in small areas (like an accent bar) where a pale tone wouldn't
    stand out - while keeping the same hue, so it's still recognisable as
    the same value."""
    r, g, b = (c / 255 for c in color)
    hue, _, _ = colorsys.rgb_to_hls(r, g, b)
    r2, g2, b2 = colorsys.hls_to_rgb(hue, ACCENT_LIGHTNESS, ACCENT_SATURATION)
    return (round(r2 * 255), round(g2 * 255), round(b2 * 255))


def build_color_maps(class_names, teacher_names, rooms, subjects):
    return {
        "class": pale_palette(class_names),
        "teacher": pale_palette(teacher_names),
        "room": pale_palette(rooms),
        "subject": pale_palette(subjects),
    }
