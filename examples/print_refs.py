# Prints the names of all symbols that reference a particular symbol. (There's
# also a method get_selected_symbols() for determining just selection
# relations.)

import kconfiglib
import sys

conf = kconfiglib.Config(sys.argv[1])

x86 = conf["X86"]
for sym in conf:
    if x86 in sym.get_referenced_symbols():
        print sym.get_name()
