# timetable_render.py
#
# Turns a solved timetable (day -> period -> class -> {subject, teacher,
# room}) into, for every class/teacher/room, a markdown grid (periods as
# rows, days as columns) AND a matching PNG of the same grid.
#
# The PNG is designed to be glanceable for one pattern at a time:
#   - the whole cell's background is the SUBJECT's colour (the thing you
#     most want to spot a pattern in, e.g. "when is P1 in English")
#   - a coloured accent bar down the left edge is the secondary category
#     (room for a class/teacher view, teacher for a room view) - e.g. "when
#     is P1 in Room 102" is then a matter of spotting a repeated bar colour
#   - the third category is shown as plain black text only, no colour
# Every value's colour is fixed globally (see timetable_colors.py), and a
# legend under the grid decodes both colour scales used in that image.

import os

from PIL import Image, ImageDraw, ImageFont

from timetable_colors import accent_variant

FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]
FONT_BOLD_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]

CELL_WIDTH = 190
CELL_HEIGHT = 96
LABEL_WIDTH = 130
HEADER_HEIGHT = 36
TITLE_HEIGHT = 34
ACCENT_WIDTH = 24
LEGEND_MARGIN = 16
LEGEND_SWATCH = 16
LEGEND_ROW_GAP = 8
LEGEND_ITEM_GAP = 20
FREE_COLOR = (238, 238, 238)
NO_SCHOOL_COLOR = (200, 200, 200)
GRID_COLOR = (110, 110, 110)
TEXT_COLOR = "black"

# category shown as the full cell background, always
BACKGROUND_CATEGORY = "subject"

# (accent category, plain-text category) for the other two values a given
# entity's diagram shows - whichever two aren't the entity itself
ACCENT_AND_TEXT_CATEGORY = {
    "class": ("room", "teacher"),
    "teacher": ("room", "class"),
    "room": ("teacher", "class"),
}

# fixed left-to-right order for the markdown table's cell text, regardless
# of which category is background/accent/text in the PNG
MARKDOWN_ORDER = {
    "class": ["subject", "teacher", "room"],
    "teacher": ["class", "subject", "room"],
    "room": ["class", "subject", "teacher"],
}


def period_time(periods, period):
    return f"{periods[period]['start_time']}-{periods[period]['end_time']}"


def safe_filename(name):
    return name.replace(" ", "_")


def build_cell_data(timetable, entity_kind, entity_name):
    """Return {(day, period): {category: value}} for every slot this entity
    is actually in. A slot that exists but is missing from this dict means
    the entity is free that slot."""

    cell_data = {}
    for day, day_periods in timetable.items():
        for period, entries in day_periods.items():
            if entity_kind == "class":
                info = entries[entity_name]
                cell_data[(day, period)] = {
                    "subject": info["subject"],
                    "teacher": info["teacher"],
                    "room": info["room"],
                }
            else:
                other_key = "room" if entity_kind == "teacher" else "teacher"
                for class_name, info in entries.items():
                    if info[entity_kind] == entity_name:
                        cell_data[(day, period)] = {
                            "class": class_name,
                            "subject": info["subject"],
                            other_key: info[other_key],
                        }
                        break
    return cell_data


def write_markdown_grid(path, title, days, periods, cell_data, entity_kind):
    day_names = list(days.keys())
    period_names = sorted(periods.keys(), key=int)
    order = MARKDOWN_ORDER[entity_kind]

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
                row.append("<br>".join(entries[category] for category in order) if entries else "*Free*")
        lines.append("| " + " | ".join(row) + " |")

    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def load_font(size, bold=False):
    for candidate in (FONT_BOLD_CANDIDATES if bold else FONT_CANDIDATES):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def fitting_font(text, max_width, sizes, bold=False):
    for size in sizes:
        font = load_font(size, bold=bold)
        if font.getlength(text) <= max_width:
            return font
    return load_font(sizes[-1], bold=bold)


def draw_centered_text(draw, box, text, font, fill=TEXT_COLOR):
    x0, y0, x1, y1 = box
    bbox = draw.textbbox((0, 0), text, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = x0 + ((x1 - x0) - w) / 2 - bbox[0]
    y = y0 + ((y1 - y0) - h) / 2 - bbox[1]
    draw.text((x, y), text, font=font, fill=fill)


def layout_legend_rows(font, items, max_width):
    """items: [(color, label), ...]. Returns rows of [(x, color, label), ...]."""
    rows, current_row, x = [], [], 0
    for color, label in items:
        item_width = LEGEND_SWATCH + 6 + font.getlength(label)
        if current_row and x + item_width > max_width:
            rows.append(current_row)
            current_row, x = [], 0
        current_row.append((x, color, label))
        x += item_width + LEGEND_ITEM_GAP
    if current_row:
        rows.append(current_row)
    return rows


def legend_height(font, items, max_width, title_font):
    if not items:
        return 0
    rows = layout_legend_rows(font, items, max_width)
    row_height = LEGEND_SWATCH + LEGEND_ROW_GAP
    return title_font.getbbox("Ag")[3] + 6 + len(rows) * row_height


def draw_legend(draw, x0, y0, title, items, max_width):
    if not items:
        return y0
    title_font = load_font(14, bold=True)
    item_font = load_font(13)

    draw.text((x0, y0), title, font=title_font, fill=TEXT_COLOR)
    y = y0 + title_font.getbbox("Ag")[3] + 6

    for row in layout_legend_rows(item_font, items, max_width):
        for x_off, color, label in row:
            sx0, sy0 = x0 + x_off, y
            sx1, sy1 = sx0 + LEGEND_SWATCH, sy0 + LEGEND_SWATCH
            draw.rectangle([sx0, sy0, sx1, sy1], fill=color, outline=GRID_COLOR)
            draw.text((sx1 + 6, sy0 - 2), label, font=item_font, fill=TEXT_COLOR)
        y += LEGEND_SWATCH + LEGEND_ROW_GAP
    return y


def write_png_grid(path, title, days, periods, cell_data, color_maps, entity_kind):
    day_names = list(days.keys())
    period_names = sorted(periods.keys(), key=int)
    accent_category, text_category = ACCENT_AND_TEXT_CATEGORY[entity_kind]

    grid_width = LABEL_WIDTH + CELL_WIDTH * len(day_names)
    grid_height = TITLE_HEIGHT + HEADER_HEIGHT + CELL_HEIGHT * len(period_names)

    used_subjects = sorted({e["subject"] for e in cell_data.values()})
    used_accents = sorted({e[accent_category] for e in cell_data.values()})

    legend_max_width = grid_width - 2 * LEGEND_MARGIN
    title_font = load_font(14, bold=True)
    item_font = load_font(13)
    subject_legend_h = legend_height(item_font, [(color_maps["subject"][v], v) for v in used_subjects], legend_max_width, title_font)
    accent_legend_h = legend_height(item_font, [(color_maps[accent_category][v], v) for v in used_accents], legend_max_width, title_font)

    height = grid_height + LEGEND_MARGIN + subject_legend_h + LEGEND_MARGIN + accent_legend_h + LEGEND_MARGIN

    image = Image.new("RGB", (grid_width, height), "white")
    draw = ImageDraw.Draw(image)

    draw_centered_text(draw, (0, 0, grid_width, TITLE_HEIGHT), title, load_font(20))

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

            subject_value = entries["subject"]
            accent_value = entries[accent_category]
            text_value = entries[text_category]

            draw.rectangle([x0, y0, x1, y1], fill=color_maps["subject"][subject_value])
            draw.rectangle([x0, y0, x0 + ACCENT_WIDTH, y1], fill=accent_variant(color_maps[accent_category][accent_value]))
            draw.rectangle([x0, y0, x1, y1], outline=GRID_COLOR)

            content_box = (x0 + ACCENT_WIDTH + 4, y0, x1 - 4, y1)
            content_width = content_box[2] - content_box[0]
            line_height = (y1 - y0) / 3

            subject_font = fitting_font(subject_value, content_width, [14, 13, 12, 11, 10, 9], bold=True)
            draw_centered_text(draw, (content_box[0], y0, content_box[2], y0 + line_height), subject_value, subject_font)

            accent_font = fitting_font(accent_value, content_width, [12, 11, 10, 9, 8])
            draw_centered_text(draw, (content_box[0], y0 + line_height, content_box[2], y0 + 2 * line_height), accent_value, accent_font)

            text_font = fitting_font(text_value, content_width, [12, 11, 10, 9, 8])
            draw_centered_text(draw, (content_box[0], y0 + 2 * line_height, content_box[2], y1), text_value, text_font)

    legend_y = grid_height + LEGEND_MARGIN
    legend_y = draw_legend(
        draw, LEGEND_MARGIN, legend_y,
        "Subject", [(color_maps["subject"][v], v) for v in used_subjects], legend_max_width,
    )
    draw_legend(
        draw, LEGEND_MARGIN, legend_y + LEGEND_MARGIN,
        accent_category.capitalize(), [(accent_variant(color_maps[accent_category][v]), v) for v in used_accents], legend_max_width,
    )

    image.save(path)


def write_entity_timetables(folder, timetable, periods, days, entity_names, entity_kind, color_maps, dir_name):
    entity_dir = os.path.join(folder, dir_name)
    os.makedirs(entity_dir, exist_ok=True)

    for entity_name in entity_names:
        cell_data = build_cell_data(timetable, entity_kind, entity_name)
        base_path = os.path.join(entity_dir, safe_filename(entity_name))

        write_markdown_grid(base_path + ".md", f"Timetable for {entity_name}", days, periods, cell_data, entity_kind)
        write_png_grid(base_path + ".png", f"Timetable for {entity_name}", days, periods, cell_data, color_maps, entity_kind)
