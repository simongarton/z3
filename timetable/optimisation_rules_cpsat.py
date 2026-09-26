# optimisation_rules_cpsat.py
#
# CP-SAT equivalents of the rules in optimisation_rules.py, for the same
# catalogue (optimisation.json) and run configuration (optimisations.json).
# Z3 expresses "count how often X happens" with If(cond, 1, 0) inside a
# Sum(); CP-SAT doesn't have a direct equivalent, so every rule here builds
# its own BoolVars via *reification* - a constraint is only enforced when a
# controlling boolean is true (`.OnlyEnforceIf(b)`), and its negation only
# when that boolean is false - then sums those BoolVars directly (a CP-SAT
# BoolVar behaves as 0/1 in a linear expression).
#
# Each rule function takes (model, ctx) and returns a CP-SAT linear
# expression: the *raw, unweighted* count for that rule, exactly like the
# Z3 version. The caller multiplies it by whatever weight optimisations.json
# gives the rule.

FAIR_SHARE_SCALE = 20


def bool_eq(model, expr_a, expr_b, name):
    """A BoolVar that's true exactly when expr_a == expr_b."""
    b = model.NewBoolVar(name)
    model.Add(expr_a == expr_b).OnlyEnforceIf(b)
    model.Add(expr_a != expr_b).OnlyEnforceIf(b.Not())
    return b


def bool_neq_value(model, expr, value, name):
    """A BoolVar that's true exactly when expr != value."""
    b = model.NewBoolVar(name)
    model.Add(expr != value).OnlyEnforceIf(b)
    model.Add(expr == value).OnlyEnforceIf(b.Not())
    return b


def bool_and(model, literals, name):
    """A BoolVar that's true exactly when every literal is true."""
    b = model.NewBoolVar(name)
    model.AddBoolAnd(literals).OnlyEnforceIf(b)
    model.AddBoolOr([lit.Not() for lit in literals]).OnlyEnforceIf(b.Not())
    return b


def ordered_period_pairs(days):
    """(day, period, next_period) for every pair of consecutive periods
    within a day, e.g. Wednesday only pairs up (1,2)...(5,6), not (6,7)."""
    pairs = []
    for day, day_periods in days.items():
        ordered = sorted(day_periods)
        for period, next_period in zip(ordered, ordered[1:]):
            pairs.append((day, str(period), str(next_period)))
    return pairs


def build_teacher_room_vars(model, ctx):
    """One IntVar per (teacher, day, period): the room index that teacher is
    in during that slot, or -1 if they're free. Built once and shared across
    every rule that needs it (rule1, rule2, rule4), the same way the Z3
    version's teacher_room_expr() was recomputed on the fly but relied on
    Z3's own structural sharing - here we build it explicitly, once."""

    class_names = ctx["class_names"]
    teacher_vars = ctx["teacher_vars"]
    room_vars = ctx["room_vars"]
    num_rooms = ctx["num_rooms"]

    troom = {}
    for day, day_periods in ctx["days"].items():
        for period in [str(p) for p in day_periods]:
            for teacher_idx in range(len(ctx["teacher_names"])):
                var = model.NewIntVar(-1, num_rooms - 1, f"troom_{teacher_idx}_{day}_{period}")
                match_bools = []
                for c in class_names:
                    b = model.NewBoolVar(f"match_{teacher_idx}_{c}_{day}_{period}")
                    model.Add(teacher_vars[(c, day, period)] == teacher_idx).OnlyEnforceIf(b)
                    model.Add(teacher_vars[(c, day, period)] != teacher_idx).OnlyEnforceIf(b.Not())
                    model.Add(var == room_vars[(c, day, period)]).OnlyEnforceIf(b)
                    match_bools.append(b)
                # Distinct (AddAllDifferent on teacher_vars) guarantees at
                # most one class can match, so "none matched" is well-defined
                model.Add(var == -1).OnlyEnforceIf([b.Not() for b in match_bools])
                troom[(teacher_idx, day, period)] = var

    return troom


def rule_teacher_same_room_next_period(model, ctx):
    """rule1: If a teacher stays in the same room for their next period,
    that is good."""
    troom = ctx.setdefault("_troom", build_teacher_room_vars(model, ctx))

    terms = []
    for day, period, next_period in ordered_period_pairs(ctx["days"]):
        for teacher_idx in range(len(ctx["teacher_names"])):
            room_now = troom[(teacher_idx, day, period)]
            room_next = troom[(teacher_idx, day, next_period)]
            tag = f"{teacher_idx}_{day}_{period}"
            not_free_now = bool_neq_value(model, room_now, -1, f"notfree_now_{tag}")
            not_free_next = bool_neq_value(model, room_next, -1, f"notfree_next_{tag}")
            same = bool_eq(model, room_now, room_next, f"same_{tag}")
            terms.append(bool_and(model, [not_free_now, not_free_next, same], f"good1_{tag}"))
    return sum(terms)


def rule_teacher_has_a_break(model, ctx):
    """rule2: If a teacher has a break between periods, that is good.

    Same interpretation as the Z3 version: a free period that isn't the
    first or last scheduled period of the day - a genuine mid-day gap.
    """
    troom = ctx.setdefault("_troom", build_teacher_room_vars(model, ctx))

    terms = []
    for day, day_periods in ctx["days"].items():
        ordered = [str(p) for p in sorted(day_periods)]
        if len(ordered) < 3:
            continue
        for period in ordered[1:-1]:
            for teacher_idx in range(len(ctx["teacher_names"])):
                room_now = troom[(teacher_idx, day, period)]
                is_free = model.NewBoolVar(f"free_{teacher_idx}_{day}_{period}")
                model.Add(room_now == -1).OnlyEnforceIf(is_free)
                model.Add(room_now != -1).OnlyEnforceIf(is_free.Not())
                terms.append(is_free)
    return sum(terms)


def rule_class_same_room_next_period(model, ctx):
    """rule3: If a class stays in the same room for their next period, that
    is good."""
    room_vars = ctx["room_vars"]
    terms = []
    for day, period, next_period in ordered_period_pairs(ctx["days"]):
        for class_name in ctx["class_names"]:
            name = f"sameroom_{class_name}_{day}_{period}"
            terms.append(
                bool_eq(model, room_vars[(class_name, day, period)], room_vars[(class_name, day, next_period)], name)
            )
    return sum(terms)


def rule_teacher_fair_daily_share(model, ctx):
    """rule4: Spread each day's lessons evenly across all teachers, rather
    than relying on the same few every time. Same "penalty, always <= 0"
    shape as the Z3 version, using CP-SAT's native AddAbsEquality and
    AddDivisionEquality instead of hand-built If()-based abs/scale."""

    class_names = ctx["class_names"]
    troom = ctx.setdefault("_troom", build_teacher_room_vars(model, ctx))
    num_teachers = len(ctx["teacher_names"])

    deviation_terms = []
    for day, day_periods in ctx["days"].items():
        periods = [str(p) for p in day_periods]
        total_lessons = len(periods) * len(class_names)

        for teacher_idx in range(num_teachers):
            busy_bools = []
            for period in periods:
                b = bool_neq_value(model, troom[(teacher_idx, day, period)], -1, f"busy_{teacher_idx}_{day}_{period}")
                busy_bools.append(b)
            count = sum(busy_bools)
            deviation = count * num_teachers - total_lessons

            abs_var = model.NewIntVar(0, num_teachers * len(periods), f"dev_{teacher_idx}_{day}")
            model.AddAbsEquality(abs_var, deviation)
            deviation_terms.append(abs_var)

    total_deviation = sum(deviation_terms)
    scaled = model.NewIntVar(0, 10_000, "fair_share_scaled")
    model.AddDivisionEquality(scaled, total_deviation, FAIR_SHARE_SCALE)
    return -scaled


def rule_subject_taught_daily(model, ctx):
    """rule5: Every subject a class studies should be taught at least once
    that day, wherever there are enough periods to fit it in. Same idea and
    same caveat as the Z3 version: a class with more subjects than a day
    has periods (S3 on Wednesday; S4 on any day) can never hit its own
    maximum that day, since each period can only be one subject - this
    rewards getting as close as possible rather than requiring it outright.
    """
    class_subjects = ctx["classes"]
    subject_vars = ctx["subject_vars"]
    subject_index = ctx["subject_index"]

    terms = []
    for day, day_periods in ctx["days"].items():
        periods = [str(p) for p in day_periods]
        for class_name, subjects in class_subjects.items():
            for subject in subjects:
                s_idx = subject_index[subject]
                period_bools = []
                for period in periods:
                    b = model.NewBoolVar(f"issubj_{class_name}_{subject}_{day}_{period}")
                    model.Add(subject_vars[(class_name, day, period)] == s_idx).OnlyEnforceIf(b)
                    model.Add(subject_vars[(class_name, day, period)] != s_idx).OnlyEnforceIf(b.Not())
                    period_bools.append(b)

                taught_today = model.NewBoolVar(f"taughtday_{class_name}_{subject}_{day}")
                model.AddBoolOr(period_bools).OnlyEnforceIf(taught_today)
                model.AddBoolAnd([b.Not() for b in period_bools]).OnlyEnforceIf(taught_today.Not())
                terms.append(taught_today)
    return sum(terms)


RULES = {
    "rule1": rule_teacher_same_room_next_period,
    "rule2": rule_teacher_has_a_break,
    "rule3": rule_class_same_room_next_period,
    "rule4": rule_teacher_fair_daily_share,
    "rule5": rule_subject_taught_daily,
}
