# Works like 'make allyesconfig'. Verified by the test suite to generate output
# identical to 'make allyesconfig', for all ARCHES.
#
# This example is implemented a bit differently from allnoconfig.py to
# demonstrate some other possibilities. A variant similar to
# allnoconfig_simpler.py could be constructed too.
#
# In theory, we need to handle choices in two different modes:
#
#   y: One symbol is y, the rest are n
#   m: Any number of symbols are m, the rest are n
#
# Only tristate choices can be in m mode.
#
# In practice, no m mode choices appear for allyesconfig as of 4.14, as
# expected, but we still handle them here for completeness. Here's a convoluted
# example of how you might get an m-mode choice even during allyesconfig:
#
#   choice
#           tristate "weird choice"
#           depends on m
#
#   ...
#
#   endchoice
#
#
# Usage:
#
#   $ make [ARCH=<arch>] scriptconfig SCRIPT=Kconfiglib/examples/allyesconfig.py

from kconfiglib import Kconfig, Choice, STR_TO_TRI
import sys

def all_choices(node):
    """
    Returns all choices in the menu tree rooted at 'node'. See the
    Kconfig.write_config() implementation in kconfiglib.py for an example of
    how the tree can be walked iteratively instead.

    (I was thinking of making a list of choices available directly in the API,
    but I'm not sure it will always be needed internally, and I'm trying to
    spam the API with less seldomly-used stuff compared to Kconfiglib 1.)
    """
    res = []

    while node:
        if isinstance(node.item, Choice):
            res.append(node.item)

        if node.list:
            res.extend(all_choices(node.list))

        node = node.next

    return res

kconf = Kconfig(sys.argv[1])

non_choice_syms = [sym for sym in kconf.defined_syms if not sym.choice]
choices = all_choices(kconf.top_node)  # All choices in the configuration

while True:
    changed = False

    for sym in non_choice_syms:
        # Set the symbol to the highest assignable value, unless it already has
        # that value. sym.assignable[-1] gives the last element in assignable.
        if sym.assignable and sym.tri_value < sym.assignable[-1]:
            sym.set_value(sym.assignable[-1])
            changed = True

    for choice in choices:
        # Same logic as above for choices
        if choice.assignable and choice.tri_value < choice.assignable[-1]:
            choice.set_value(choice.assignable[-1])
            changed = True

            # For y-mode choices, we just let the choice get its default
            # selection. For m-mode choices, we set all choice symbols to m.
            if choice.tri_value == 1:
                for sym in choice.syms:
                    sym.set_value(1)

    # Do multiple passes until we longer manage to raise any symbols or
    # choices, like in allnoconfig.py
    if not changed:
        break

kconf.write_config(".config")
