

with open('self-executing-child.py', 'w') as output:
    output.write("print('Hello from the self-executing child script!')\n")

import subprocess
subprocess.run(['python', 'self-executing-child.py'])
