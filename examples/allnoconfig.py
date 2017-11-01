# Works like 'make allnoconfig'. Verified by the test suite to generate
# identical output to 'make allnoconfig' for all ARCHes.
#
# See allnoconfig_simpler.py for a much simpler version. This more roundabout
# version demonstrates some tree walking and value processing.
#
# Usage:
#
#   $ make [ARCH=<arch>] scriptconfig SCRIPT=Kconfiglib/examples/allnoconfig.py

from kconfiglib import Kconfig, Symbol, STR_TO_TRI
import sys

def do_allnoconfig(node):
    global changed

    # Walk the tree of menu nodes. You can imagine this as going down/into menu
    # entries in the menuconfig interface, setting each to 'n' (or the lowest
    # assignable value).

    while node is not None:
        if isinstance(node.item, Symbol):
            sym = node.item

            # Is the symbol a non-choice, non-allnoconfig_y symbol that can be
            # set to a lower value than its current value?
            if (sym.choice is None and
                not sym.is_allnoconfig_y and
                sym.assignable and
                sym.assignable[0] < sym.tri_value):

                # Yup, lower it
                sym.set_value(sym.assignable[0])
                changed = True

        # Recursively lower children
        if node.list is not None:
            do_allnoconfig(node.list)

        node = node.next

conf = Kconfig(sys.argv[1])

# Do an initial pass to set 'option allnoconfig_y' symbols to 'y'
for sym in conf.defined_syms:
    if sym.is_allnoconfig_y:
        sym.set_value(2)

while 1:
    # Changing later symbols in the configuration can sometimes allow earlier
    # symbols to be lowered, e.g. if a later symbol 'select's an earlier
    # symbol. To handle such situations, we do additional passes over the tree
    # until we're no longer able to change the value of any symbol in a pass.
    changed = False

    do_allnoconfig(conf.top_node)

    # Did the pass change any symbols?
    if not changed:
        break

conf.write_config(".config")
