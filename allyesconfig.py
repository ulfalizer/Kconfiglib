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
# The default output filename is '.config'. A different filename can be passed
# in the KCONFIG_CONFIG environment variable.
#
# Usage for the Linux kernel:
#
#   $ make [ARCH=<arch>] scriptconfig SCRIPT=Kconfiglib/examples/allyesconfig.py

import kconfiglib

def main():
    kconf = kconfiglib.standard_kconfig()

    # See allnoconfig.py
    kconf.disable_warnings()

    # Try to set all symbols to 'y'. Dependencies might truncate the value down
    # later, but this will at least give the highest possible value.
    #
    # Assigning 0/1/2 to non-bool/tristate symbols has no effect (int/hex
    # symbols still take a string, because they preserve formatting).
    #
    # The set() speeds things up for projects that use multiple definition
    # locations a lot
    for sym in set(kconf.defined_syms):
        # Set choice symbols to 'm'. This value will be ignored for choices in
        # 'y' mode (the "normal" mode), which will instead just get their
        # default selection, but will set all symbols in m-mode choices to 'm',
        # which is as high as they can go.
        sym.set_value(1 if sym.choice else 2)

    # Set all choices to the highest possible mode
    for choice in kconf.choices:
        choice.set_value(2)

    kconf.write_config(kconfiglib.standard_config_filename())

if __name__ == "__main__":
    main()
