from z3 import *


## [.##.] (3) (1,3) (2) (2,3) (0,2) (0,1) {3,5,4,7}

# I need some variables to store the 4 joltages at the end.
j0 = Int('j0')
j1 = Int('j1')
j2 = Int('j2')
j3 = Int('j43')

# how many buttons do I have to press?
b0_presses = Int('b0_presses')
b1_presses = Int('b1_presses')
b2_presses = Int('b2_presses')
b3_presses = Int('b3_presses')
b4_presses = Int('b4_presses')
b5_presses = Int('b5_presses')



# I want to solve it so that j1 is 3
solve(
    ## j0
    b4_presses + b5_presses == 3,
    ## j1
    b1_presses + b5_presses == 5,
    ## j2
    b2_presses + b3_presses + b4_presses == 4,
    ## j3
    b0_presses + b1_presses + b3_presses == 7,

    # sanity
    b0_presses >= 0,
    b1_presses >= 0,
    b2_presses >= 0,
    b3_presses >= 0,
    b4_presses >= 0,
    b5_presses >= 0
    )

