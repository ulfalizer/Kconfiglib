# Prints the names of all symbols that are referenced but never defined in the
# current configuration together with the locations where they are referenced.
# Integers being included in the list is not a bug, as these need to be treated
# as symbols per the design of Kconfig.

import kconfiglib
import sys

conf = kconfiglib.Config(sys.argv[1])

for sym in conf.get_symbols():
    if not sym.is_defined():
        print sym.get_name()
        for (filename, linenr) in sym.get_ref_locations():
            print "  {0}:{1}".format(filename, linenr)
