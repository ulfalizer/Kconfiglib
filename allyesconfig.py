#!/usr/bin/env python

# Works like 'make allyesconfig'. Verified by the test suite to generate output
# identical to 'make allyesconfig', for all ARCHES.
#
# In theory, we need to handle choices in two different modes:
#
#   y: One symbol is y, the rest are n
#   m: Any number of symbols are m, the rest are n
#
# Only tristate choices can be in m mode.
#
# Here's a convoluted example of how you might get an m-mode choice even during
# allyesconfig:
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
# Usage for the Linux kernel:
#
#   $ make [ARCH=<arch>] scriptconfig SCRIPT=Kconfiglib/examples/allyesconfig.py

import os
import sys

import kconfiglib

def main():
    kconf = kconfiglib.standard_kconfig()

    # Avoid warnings printed by Kconfiglib when assigning a value to a symbol that
    # has no prompt. Such assignments never have an effect.
    kconf.disable_warnings()

    # Small optimization
    BOOL_TRI = (kconfiglib.BOOL, kconfiglib.TRISTATE)

    for sym in kconf.defined_syms:
        if sym.orig_type in BOOL_TRI and not sym.choice:
            sym.set_value(2)

    # This might be slightly more robust than what the C tools do for choices,
    # as raising one choice might allow other choices to be raised. It
    # currently produces the same output for all ARCHes though.

    while True:
        changed = False

        for choice in kconf.choices:
            if choice.assignable and choice.tri_value < choice.assignable[-1]:
                choice.set_value(choice.assignable[-1])

                # For y-mode choices, we just let the choice get its default
                # selection. For m-mode choices, we set all choice symbols to
                # m.
                if choice.tri_value == 1:
                    for sym in choice.syms:
                        sym.set_value(1)

                changed = True

        # Do multiple passes until we longer manage to raise any choices, like
        # in allnoconfig_walk.py
        if not changed:
            break

    kconf.write_config(".config")

if __name__ == "__main__":
    main()
