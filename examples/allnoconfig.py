# Works like 'make allnoconfig'. Verified by the test suite to generate
# identical output to 'make allnoconfig' for all ARCHes.
#
# See allnoconfig_simpler.py for a much simpler version. This version
# demonstrates some tree walking and value processing.
#
# Usage:
#
#   $ make [ARCH=<arch>] scriptconfig SCRIPT=Kconfiglib/examples/allnoconfig.py

from kconfiglib import Config, Symbol, tri_less
import sys

def do_allnoconfig(node):
    global no_changes

    # Walk the tree of menu nodes. You can imagine this as going down/into menu
    # entries in the menuconfig interface, setting each to 'n' (or the lowest
    # assignable value).

    while node is not None:
        if isinstance(node.item, Symbol):
            sym = node.item

            # Is the symbol a non-choice symbol that can be set to a lower
            # value than its current value?
            if sym.choice is None and sym.assignable and \
               tri_less(sym.assignable[0], sym.value):

                # Yup, lower it
                sym.set_value(sym.assignable[0])
                no_changes = False

        # Recursively lower children
        if node.list is not None:
            do_allnoconfig(node.list)

        node = node.next

conf = Config(sys.argv[1])

while 1:
    # For tricky dependencies involving '!', setting later symbols to 'n' might
    # actually raise the value of earlier symbols. To be super safe, we do
    # additional passes until a pass no longer changes the value of any symbol.
    #
    # This isn't actually needed for any ARCH in the kernel as of 4.14. A
    # single pass gives the correct result.
    no_changes = True

    do_allnoconfig(conf.top_menu)

    # Did the pass change any symbols?
    if no_changes:
        break

conf.write_config(".config")
