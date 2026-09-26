import subprocess
import os

def get_data(line):
    parts = line.strip().split()
    lights = parts[0]
    buttons = [x for x in parts[1:-1]]
    joltages = [int(x) for x in parts[-1].strip('{}').split(',')]
    return lights, buttons, joltages

def build_and_execute(line, index):

    # this is what a line will look like, with variable numbers of each section
    # [.##.] (3) (1,3) (2) (2,3) (0,2) (0,1) {3,5,4,7}

    lights, buttons, joltages = get_data(line)
    print("Lights:", lights)
    print("Buttons:", buttons )
    print("Joltages:", joltages )

    file_data = []
    file_data.append("from z3 import *")
    file_data.append("")

    file_data.append("# I need some variables to store the 4 joltages at the end.")
    file_data.append("")

    for joltage_index in range(len(joltages)):
        file_data.append(f"j{joltage_index} = Int('j{joltage_index}')")
    file_data.append("")

    file_data.append("# how many buttons do I have to press?")
    file_data.append("")

    for button_index in range(len(buttons)):
        file_data.append(f"b{button_index}_presses = Int('b{button_index}_presses')")
    file_data.append("")
    file_data.append("o = Optimize()")
    file_data.append("")
    file_data.append("# I want to solve it so that j1 is 3")
    file_data.append("o.add(")
    for joltage_index in range(len(joltages)):
        presses = " + ".join([f"b{button_index}_presses" for button_index in range(len(buttons)) if str(joltage_index) in buttons[button_index]])
        file_data.append(f"    ## j{joltage_index}")
        file_data.append(f"    {presses} == {joltages[joltage_index]},")
    file_data.append("")
    file_data.append("    # sanity")
    for button_index in range(len(buttons)):
        file_data.append(f"    b{button_index}_presses >= 0,")
    file_data.append("    )")
    file_data.append("")
    file_data.append("o.minimize(" + " + ".join([f"b{button_index}_presses" for button_index in range(len(buttons))]) + ")")
    file_data.append("")
    file_data.append("if o.check() == sat:")
    file_data.append("    model = o.model()")
    for button_index in range(len(buttons)):
        file_data.append(f"    b{button_index}_pressed = model[b{button_index}_presses].as_long()")
    file_data.append("")
    file_data.append("    total = " + " + ".join([f"b{button_index}_pressed" for button_index in range(len(buttons))]))
    file_data.append('    print("Button presses:" )')
    for button_index in range(len(buttons)):
        file_data.append(f'    print("Button {button_index} pressed:", b{button_index}_pressed)')
    file_data.append('    with open("2025-10.mega-output.txt", "a") as output_file:')
    file_data.append('        output_file.write(f"{total}\\n")')
    file_data.append("else:")
    file_data.append('    print("Problem is unsatisfiable")')

    script_name = f"mega_temp_script_{index}.py"
    with open(script_name, "w") as f:
        f.write("\n".join(file_data))
    subprocess.run(['python', script_name])
    os.remove(script_name)


with open("part1.txt", "r") as f:
    try:
        os.remove('2025-10.mega-output.txt')
    except FileNotFoundError:
        pass
    lines = f.readlines()
    index = 0
    for line in lines:
        build_and_execute(line, index)
        index += 1


    with open('2025-10.mega-output.txt', 'r') as output_file:
        results = output_file.readlines()
        total_presses = sum(int(x.strip()) for x in results)
        print("Total button presses across all lines:", total_presses)
