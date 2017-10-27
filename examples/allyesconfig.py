# Works like 'make allyesconfig'. Verified by the test suite to generate
# identical output to 'make allyesconfig' for all ARCHES.
#
# This could be implemented as a straightforward tree walk just like
# allnoconfig.py (or even simpler like allnoconfig_simpler.py), but do it a bit
# differently (roundabout) just to demonstrate some other possibilities.
#
# allyesconfig is a bit more involved than allnoconfig as we need to handle
# choices in two different modes:
#
#   y: One symbol is "y", the rest are "n"
#   m: Any number of symbols are "m", the rest are "n"
#
# Only tristate choices can be in "m" mode. No "m" mode choices seem to appear
# for allyesconfig on the kernel Kconfigs as of 4.14, but we still handle it.
#
# Usage:
#
#   $ make [ARCH=<arch>] scriptconfig SCRIPT=Kconfiglib/examples/allyesconfig.py

from kconfiglib import Config, Choice, STR_TO_TRI
import sys

conf = Config(sys.argv[1])

# Collect all the choices in the configuration. Demonstrates how the menu node
# tree can be walked iteratively by using the parent pointers.

choices = []
node = conf.top_node

while 1:
    if isinstance(node.item, Choice):
        choices.append(node.item)

    # Iterative tree walking by using parent pointers.
    #
    # Recursing on next pointers can blow the Python stack. Recursing on child
    # pointers is safe (as is done in the other examples). This gives a
    # template for how you can avoid recursing on both. The same logic is found
    # in the C implementation.

    if node.list is not None:
        # Jump to child node if available
        node = node.list

    elif node.next is not None:
        # Otherwise, jump to next node if available
        node = node.next

    else:
        # Otherwise, look for parents with next nodes to jump to
        while node.parent is not None:
            node = node.parent
            if node.next is not None:
                node = node.next
                break
        else:
            # No parents with next nodes, all nodes visited
            break

# Collect all symbols that are not in choices
non_choice_syms = [sym for sym in conf.defined_syms if sym.choice is None]

while 1:
    no_changes = True

    # Handle symbols outside of choices

    for sym in non_choice_syms:
        # See allnoconfig example. [-1] gives the last (highest) assignable
        # value.
        if sym.assignable and sym.tri_value < STR_TO_TRI[sym.assignable[-1]]:
            sym.set_value(sym.assignable[-1])
            no_changes = False

    # Handle choices

    for choice in choices:
        # Handle a choice whose visibility allows it to be in "y" mode

        if choice.visibility == 2:
            selection = choice.default_selection

            # Does the choice have a default selection that we haven't already
            # selected?
            if selection is not None and \
               selection is not choice.user_selection:

                # Yup, select it
                selection.set_value("y")
                no_changes = False

        # Handle a choice whose visibility only allows it to be in "m" mode.
        # This might happen if a choice depends on a symbol that can only be
        # "m", for example.

        elif choice.visibility == 1:
            for sym in choice.symbols:

                # Does the choice have a symbol that can be "m" that we haven't
                # already set to "m"?
                if sym.user_tri_value != 1 and "m" in sym.assignable:

                    # Yup, set it
                    sym.set_value("m")
                    no_changes = False

    if no_changes:
        break

conf.write_config(".config")
