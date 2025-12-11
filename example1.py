from z3 import *

# 1. Declare variables
x = Int('x')
y = Int('y')

# 2. State constraints and find a solution using the solve function
solve(x > 2, y < 10, x + 2*y == 7)
