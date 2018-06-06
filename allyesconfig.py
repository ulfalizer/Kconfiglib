#!/usr/bin/env python

# Copyright (c) 2018, Ulf Magnusson
# SPDX-License-Identifier: ISC

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

import kconfiglib

def main():
    kconf = kconfiglib.standard_kconfig()

    # Avoid warnings printed by Kconfiglib when assigning a value to a symbol that
    # has no prompt. Such assignments never have an effect.
    kconf.disable_warnings()

    # Small optimization
    BOOL_TRI = (kconfiglib.BOOL, kconfiglib.TRISTATE)

    # Try to set all bool/tristate symbols to 'y'. Dependencies might truncate
    # the value down later, but this will at least give the highest possible
    # value.
    for sym in kconf.defined_syms:
        if sym.orig_type in BOOL_TRI:
            # Set all choice symbols to 'm'. This value will be ignored for
            # choices in 'y' mode (the "normal" mode), but will set all symbols
            # in m-mode choices to 'm', which is as high as they can go.
            sym.set_value(1 if sym.choice else 2)

    # Set all choices to the highest possible mode
    for choice in kconf.choices:
        choice.set_value(2)

    kconf.write_config(kconfiglib.standard_config_filename())

if __name__ == "__main__":
    main()
