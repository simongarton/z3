from z3 import *


def trivial():

    x = Int('x')

    solve(x + 2 == 4)

# more programmy

def solve_equation():

    x = Int('x')

    s = Solver()
    s.add(x + 2 == 4)

    if s.check() == sat:
        m = s.model()
        result = m[x].as_long()   # Python int, e.g. 2
        print(result)
        return result
    else:
        print("no solution")
        return None

if __name__ == "__main__":
    solve_equation()
