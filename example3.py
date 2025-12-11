from z3 import *


set_option(html_mode=True)
x = Int('x')
y = Int('y')
print (x**2 + y**2 >= 1)
set_option(html_mode=False)
print (x**2 + y**2 >= 1)
