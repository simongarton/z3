# optimisation_rules.py
#
# The scoring rules referenced by timetable/optimisation.json. Each rule id
# there is just a plaintext description - Z3 can't turn English into a
# constraint, so each one needs a matching function here that expresses the
# same idea as a Z3 expression counting how often it happens in the
# timetable being built.
#
# A rule function takes a `ctx` dict (see generate_optimal_timetable.py) and
# returns a single Z3 IntExpr: the *raw, unweighted* number of times that
# pattern occurs. The caller multiplies this by whatever weight this run's
# optimisations.json gives the rule.
#
# Adding a new rule to optimisation.json doesn't do anything by itself - it
# only takes effect once a function for it is added to RULES below, and it's
# referenced (with a weight) in optimisations.json.

from z3 import And, If, Sum


def ordered_period_pairs(days):
    """(day, period, next_period) for every pair of consecutive periods
    within a day, e.g. Wednesday only pairs up (1,2)...(5,6), not (6,7)."""
    pairs = []
    for day, day_periods in days.items():
        ordered = sorted(day_periods)
        for period, next_period in zip(ordered, ordered[1:]):
            pairs.append((day, str(period), str(next_period)))
    return pairs


def teacher_room_expr(ctx, day, period, teacher_idx):
    """The room index a teacher is in during a slot, or -1 if they are free
    that slot. Works because `Distinct` on teacher_vars guarantees at most
    one class can match a given teacher in a given slot, so this sum is
    either 0 (no match, i.e. free -> -1 after the offset) or the matching
    class's (room index + 1)."""
    class_names = ctx["class_names"]
    teacher_vars = ctx["teacher_vars"]
    room_vars = ctx["room_vars"]
    return (
        Sum(
            [
                If(teacher_vars[(c, day, period)] == teacher_idx, room_vars[(c, day, period)] + 1, 0)
                for c in class_names
            ]
        )
        - 1
    )


def rule_teacher_same_room_next_period(ctx):
    """rule1: If a teacher stays in the same room for their next period,
    that is good."""
    terms = []
    for day, period, next_period in ordered_period_pairs(ctx["days"]):
        for teacher_idx in range(len(ctx["teacher_names"])):
            room_now = teacher_room_expr(ctx, day, period, teacher_idx)
            room_next = teacher_room_expr(ctx, day, next_period, teacher_idx)
            terms.append(If(And(room_now != -1, room_next != -1, room_now == room_next), 1, 0))
    return Sum(terms)


def rule_teacher_has_a_break(ctx):
    """rule2: If a teacher has a break between periods, that is good.

    Interpreted as: a free (non-teaching) period that isn't the first or
    last scheduled period of the day for that teacher's school day - i.e. a
    genuine gap in the middle of the day, not just finishing early or
    starting late.
    """
    terms = []
    for day, day_periods in ctx["days"].items():
        ordered = [str(p) for p in sorted(day_periods)]
        if len(ordered) < 3:
            continue
        for period in ordered[1:-1]:
            for teacher_idx in range(len(ctx["teacher_names"])):
                room_now = teacher_room_expr(ctx, day, period, teacher_idx)
                terms.append(If(room_now == -1, 1, 0))
    return Sum(terms)


def rule_class_same_room_next_period(ctx):
    """rule3: If a class stays in the same room for their next period, that
    is good."""
    terms = []
    room_vars = ctx["room_vars"]
    for day, period, next_period in ordered_period_pairs(ctx["days"]):
        for class_name in ctx["class_names"]:
            terms.append(
                If(room_vars[(class_name, day, period)] == room_vars[(class_name, day, next_period)], 1, 0)
            )
    return Sum(terms)


FAIR_SHARE_SCALE = 20


def rule_teacher_fair_daily_share(ctx):
    """rule4: Spread each day's lessons evenly across all teachers, rather
    than relying on the same few every time.

    Unlike the other rules, this isn't a count of good events - it's a
    penalty (always <= 0) for how far each teacher's day is from an equal
    share of that day's lessons, so "more" (closer to 0) is still "better",
    consistent with how every other rule's raw score works.

    A teacher's fair share of a day with `total` lessons is total /
    num_teachers, generally not a whole number. To stay in exact integer
    arithmetic (Z3 Ints, no rounding surprises), both sides of the
    comparison are scaled by num_teachers instead of dividing: comparing
    (count * num_teachers) against total directly.

    That raw deviation sum runs into the hundreds - much bigger than rule1-3
    ever get - and optimisations.json's weights have to stay whole numbers
    (the scoring pipeline needs an exact Int total, and a fractional weight
    would turn it into a Real that .as_long() can't read). So the result is
    divided down by FAIR_SHARE_SCALE before being returned, to bring a
    weight of 1 down to a similar order of magnitude as the other rules
    instead of swamping them.

    This is a whole-day (not just consecutive-period) measure, but it's
    still entirely local to one day, so it fits the day-by-day optimizer
    fine - it just can't see or balance across the other days.
    """
    class_names = ctx["class_names"]
    teacher_vars = ctx["teacher_vars"]
    num_teachers = len(ctx["teacher_names"])

    terms = []
    for day, day_periods in ctx["days"].items():
        periods = [str(p) for p in day_periods]
        total_lessons = len(periods) * len(class_names)

        for teacher_idx in range(num_teachers):
            count = Sum(
                [
                    If(teacher_vars[(c, day, period)] == teacher_idx, 1, 0)
                    for period in periods
                    for c in class_names
                ]
            )
            deviation = count * num_teachers - total_lessons
            terms.append(If(deviation >= 0, deviation, -deviation))

    return -Sum(terms) / FAIR_SHARE_SCALE


RULES = {
    "rule1": rule_teacher_same_room_next_period,
    "rule2": rule_teacher_has_a_break,
    "rule3": rule_class_same_room_next_period,
    "rule4": rule_teacher_fair_daily_share,
}
