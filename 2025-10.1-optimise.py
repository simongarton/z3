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

total = Int("total")

o = Optimize()


# I want to solve it so that j1 is 3
o.add(
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
    b5_presses >= 0,

        # total
    # total = b0_presses + b1_presses + b2_presses + b3_presses + b4_presses + b5_presses
    )

o.minimize(b0_presses + b1_presses + b2_presses + b3_presses + b4_presses + b5_presses)

if o.check() == sat:
    model = o.model()
    print(type(model))
    b0_pressed = model[b0_presses].as_long()
    b1_pressed = model[b1_presses].as_long()
    b2_pressed = model[b2_presses].as_long()
    b3_pressed = model[b3_presses].as_long()
    b4_pressed = model[b4_presses].as_long()
    b5_pressed = model[b5_presses].as_long()

    print("Button presses:" )
    print("b0:", b0_pressed)
    print("b1:", b1_pressed)
    print("b2:", b2_pressed)
    print("b3:", b3_pressed)
    print("b4:", b4_pressed)
    print("b5:", b5_pressed)

    total = (model[b0_presses].as_long() +
             model[b1_presses].as_long() +
             model[b2_presses].as_long() +
             model[b3_presses].as_long() +
             model[b4_presses].as_long() +
             model[b5_presses].as_long())
    print("Total button presses:", total)
    with open("2025-10.1-optimise-output.txt", "a") as output_file:
        output_file.write(f"{total}\n")

else:
    print("Problem is unsatisfiable")
