# A Different Question: How Few Teachers Could Run This School?

Every post so far in this series has taken the teaching staff as fixed and asked how to schedule them well. This one flips the question: given only the classes and the subjects they need, and a deliberately unrealistic assumption - teachers never need a break, and one teacher can cover every class needing their subject at once, with no scheduling conflict possible - what's the smallest staff that could still run the school at all?

Removing the scheduling constraint turns this into a completely different, much smaller kind of problem. In the real timetable, a school needs several teachers qualified for a busy subject like English just so classes needing English at the same time aren't stuck. Take away the scheduling limit, and that redundancy stops being necessary - one qualified teacher can teach English to everyone who needs it, simultaneously, by assumption. All that's left is coverage: every subject some class needs has to be taught by *somebody*. That's a classic **minimum set cover** problem - pick the fewest teachers from the current roster whose combined subjects cover every subject in demand.

## Solving it

Twelve subjects need covering across the ten classes (English, Maths, Science, Geography, History, Art, Biology, Chemistry, Physics, Geology, Economics, Business Studies), pulled straight from `classes.json`. Each of the 12 teachers on staff has a fixed subject list. A Z3 `Bool` per teacher, one constraint per subject ("at least one qualified, retained teacher covers this"), and `Optimize().minimize()` on the headcount finds the smallest sufficient roster - then a second pass, pinning the count and enumerating with the usual "find one, block it, find the next" loop, finds every roster that ties for smallest.

```python
for subject in subjects_needed:
    qualified = [teacher_vars[name] for name, subs in teachers.items() if subject in subs]
    s.add(Or(qualified))

o.minimize(Sum([If(teacher_vars[name], 1, 0) for name in teacher_names]))
```

## The answer: 6, not 12

Half the current staff turns out to be surplus to requirements, and there are four different ways to pick the other half.

Four teachers are unavoidable, each the *only* person qualified for something a class needs: Professor Pink (the sole Geology teacher), Professor Magenta (sole Science teacher, also covers Art and Biology), Professor Navy (sole Physics teacher, also covers Biology and Economics), and Professor Indigo (sole Geography teacher, also covers Business Studies and History). Between them, those four cover 9 of the 12 subjects for free, just by being the only option for anything.

That leaves English, Maths and Chemistry needing a home, and no remaining teacher covers all three at once - so it takes exactly two more people to close the gap, giving four equally good ways to finish the roster:

| Roster | The last two picks |
|---|---|
| 1 | Gold (Chemistry, Maths) + Purple (English) |
| 2 | Gold (Chemistry, Maths) + Grey (English) |
| 3 | Gold (Chemistry, Maths) + Olive (English, Chemistry, Business Studies) |
| 4 | White (Maths) + Olive (English, Chemistry, Business Studies) |

4 (forced) + 2 (to close the gap) = **6**, and Z3 confirms there's no way to do it in 5.

## Why this doesn't mean firing six teachers

The other six exist in the real school for exactly the reason this exercise assumes away: teachers can only be in one room at a time, and busy subjects need enough qualified people that classes needing the same subject in the same period aren't left without a teacher. Strip that constraint out and the "true" minimum staff for subject coverage alone is half the size - which is really a measurement of how much of the current staffing is *redundancy for scheduling flexibility*, not a serious staffing proposal. It's a nice illustration, though, of how much a single assumption - "can this resource be in more than one place at once?" - changes which kind of problem you're even solving: from a hard, symmetric, cardinality-heavy scheduling problem down to a small, classic combinatorial-optimisation exercise that Z3 clears in a fraction of a second.
