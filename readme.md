# z3

[z3](https://www.microsoft.com/en-us/research/project/z3-3/) is a constraints solver - it's got a fancy title, but basically allows you to express problems in certain logical ways, and quickly/efficiently solve.

There are [online playgrounds](https://microsoft.github.io/z3guide/) and support for various languages. I'm using Python's `z3` ... I see [z3-solver](https://github.com/z3prover/z3) shows up more easily in searches. Oh, they are the same, it's just the import is simpler.

## examples

### trivial

```
    x = Int('x')
    solve(x + 2 == 4)
```

You can test if there was a solution (it's `2`, by the way) by expanding it a bit more:

```
    x = Int('x')
    s = Solver()
    s.add(x + 2 == 4)

    if s.check() == sat:
        m = s.model()
        return  m[x].as_long()
    else:
        return None
```

[Example 0](./example0.py)

### trivial only less so

```
x > 2, y < 10, x + 2*y == 7
```

[Example 1](./example1.py)

### making change - dumb

First the dumb version - can we simply make change for a given amount from certain coins ? In my example,
I don't have pennies - so only numbers divisible by 5 work. But the solutions are dumb - making 50c with 5x10c counts, rather than two quarters. (Don't know why not 10x5c ?)

[Making Change - Dumb](./making_change_dumb.py)

### making change - optimisation

Now we add some optimisation in : the minimal number of coins, now including pennies.

[Making Change](./making_change.py)

### advent of code

The puzzle on day 10 of 2025 (https://adventofcode.com/2025/day/10) caused a fuss. You can solve part 2 in various ways, but doing it with Z3 was trivial - should it be allowed.

Basically you have a bunch of buttons to press, each of which changes the voltage in certain ways - what's the minimum number of presses needed to do a certain thing ? Technically possible from first principles, but vast search space.

But I liked it, because I got to learn how to use z3.

[AoC2025.10](./advent-of-code/2025-10.1-optimise.py)

### course planner

Now I'm working up to the actual example I want to solve.  Here's a halfway step.

I'm a student at a university. I want to first list all combinations of courses offered that I could take - they happen on certain days and times, and I need to avoid clashes - and then second optimise it, so I'm spending the most possible time in class (doh !)

## presentations

https://theory.stanford.edu/~nikolaj/nus.html#/sec-z3 gets into maths quickly.

## older stuff

https://ericpony.github.io/z3py-tutorial/guide-examples.htm

This has a max/min example

https://www.cs.toronto.edu/~victorn/tutorials/z3/SMT.html
