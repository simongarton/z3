# timetable_render.py
#
# Turns a solved timetable (day -> period -> class -> {subject, teacher,
# room}) into, for every class/teacher/room, a markdown grid (periods as
# rows, days as columns) AND a matching PNG of the same grid, coloured so
# that each of the 3 values shown in a cell gets a pale background in that
# value's own consistent colour (see timetable_colors.py).

import os

from PIL import Image, ImageDraw, ImageFont

FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]

CELL_WIDTH = 190
CELL_HEIGHT = 96
LABEL_WIDTH = 130
HEADER_HEIGHT = 36
TITLE_HEIGHT = 34
FREE_COLOR = (238, 238, 238)
NO_SCHOOL_COLOR = (200, 200, 200)
GRID_COLOR = (110, 110, 110)
TEXT_COLOR = "black"


def period_time(periods, period):
    return f"{periods[period]['start_time']}-{periods[period]['end_time']}"


def safe_filename(name):
    return name.replace(" ", "_")


def build_cell_data(timetable, entity_kind, entity_name):
    """Return {(day, period): [(category, value), (category, value), (category, value)]}
    for every slot this entity is actually in. A slot that exists but is
    missing from this dict means the entity is free that slot."""

    cell_data = {}
    for day, day_periods in timetable.items():
        for period, entries in day_periods.items():
            if entity_kind == "class":
                info = entries[entity_name]
                cell_data[(day, period)] = [
                    ("subject", info["subject"]),
                    ("teacher", info["teacher"]),
                    ("room", info["room"]),
                ]
            else:
                other_key = "room" if entity_kind == "teacher" else "teacher"
                for class_name, info in entries.items():
                    if info[entity_kind] == entity_name:
                        cell_data[(day, period)] = [
                            ("class", class_name),
                            ("subject", info["subject"]),
                            (other_key, info[other_key]),
                        ]
                        break
    return cell_data


def write_markdown_grid(path, title, days, periods, cell_data):
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
                entries = cell_data.get((day, period))
                row.append("<br>".join(value for _, value in entries) if entries else "*Free*")
        lines.append("| " + " | ".join(row) + " |")

    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def load_font(size):
    for candidate in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def fitting_font(draw, text, max_width, sizes):
    for size in sizes:
        font = load_font(size)
        bbox = draw.textbbox((0, 0), text, font=font)
        if bbox[2] - bbox[0] <= max_width:
            return font
    return load_font(sizes[-1])


def draw_centered_text(draw, box, text, font, fill=TEXT_COLOR):
    x0, y0, x1, y1 = box
    bbox = draw.textbbox((0, 0), text, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = x0 + ((x1 - x0) - w) / 2 - bbox[0]
    y = y0 + ((y1 - y0) - h) / 2 - bbox[1]
    draw.text((x, y), text, font=font, fill=fill)


def write_png_grid(path, title, days, periods, cell_data, color_maps):
    day_names = list(days.keys())
    period_names = sorted(periods.keys(), key=int)

    width = LABEL_WIDTH + CELL_WIDTH * len(day_names)
    height = TITLE_HEIGHT + HEADER_HEIGHT + CELL_HEIGHT * len(period_names)

    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)

    draw_centered_text(draw, (0, 0, width, TITLE_HEIGHT), title, load_font(20))

    top = TITLE_HEIGHT
    draw.rectangle([0, top, LABEL_WIDTH, top + HEADER_HEIGHT], outline=GRID_COLOR)
    for c, day in enumerate(day_names):
        x0 = LABEL_WIDTH + c * CELL_WIDTH
        x1 = x0 + CELL_WIDTH
        draw.rectangle([x0, top, x1, top + HEADER_HEIGHT], outline=GRID_COLOR)
        draw_centered_text(draw, (x0, top, x1, top + HEADER_HEIGHT), day, load_font(15))

    top += HEADER_HEIGHT
    for r, period in enumerate(period_names):
        y0 = top + r * CELL_HEIGHT
        y1 = y0 + CELL_HEIGHT

        draw.rectangle([0, y0, LABEL_WIDTH, y1], outline=GRID_COLOR)
        draw_centered_text(draw, (0, y0, LABEL_WIDTH, y1), f"P{period}  {period_time(periods, period)}", load_font(12))

        for c, day in enumerate(day_names):
            x0 = LABEL_WIDTH + c * CELL_WIDTH
            x1 = x0 + CELL_WIDTH

            if period not in [str(p) for p in days[day]]:
                draw.rectangle([x0, y0, x1, y1], fill=NO_SCHOOL_COLOR, outline=GRID_COLOR)
                draw_centered_text(draw, (x0, y0, x1, y1), "-", load_font(14))
                continue

            entries = cell_data.get((day, period))
            if not entries:
                draw.rectangle([x0, y0, x1, y1], fill=FREE_COLOR, outline=GRID_COLOR)
                draw_centered_text(draw, (x0, y0, x1, y1), "Free", load_font(13))
                continue

            band_height = (y1 - y0) / len(entries)
            for i, (category, value) in enumerate(entries):
                by0 = y0 + i * band_height
                by1 = by0 + band_height
                color = color_maps[category][value]
                draw.rectangle([x0, by0, x1, by1], fill=color)
                font = fitting_font(draw, value, CELL_WIDTH - 10, [13, 12, 11, 10, 9, 8])
                draw_centered_text(draw, (x0, by0, x1, by1), value, font)

            draw.rectangle([x0, y0, x1, y1], outline=GRID_COLOR)

    image.save(path)


def write_entity_timetables(folder, timetable, periods, days, entity_names, entity_kind, color_maps, dir_name):
    entity_dir = os.path.join(folder, dir_name)
    os.makedirs(entity_dir, exist_ok=True)

    for entity_name in entity_names:
        cell_data = build_cell_data(timetable, entity_kind, entity_name)
        base_path = os.path.join(entity_dir, safe_filename(entity_name))

        write_markdown_grid(base_path + ".md", f"Timetable for {entity_name}", days, periods, cell_data)
        write_png_grid(base_path + ".png", f"Timetable for {entity_name}", days, periods, cell_data, color_maps)
