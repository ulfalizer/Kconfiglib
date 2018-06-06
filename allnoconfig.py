#!/usr/bin/env python

# Copyright (c) 2018, Ulf Magnusson
# SPDX-License-Identifier: ISC

# Works like 'make allnoconfig'. Verified by the test suite to generate
# identical output to 'make allnoconfig' for all ARCHes.
#
# See the examples/allnoconfig_walk.py example script for another variant.
#
# Usage for the Linux kernel:
#
#   $ make [ARCH=<arch>] scriptconfig SCRIPT=Kconfiglib/allnoconfig.py

import kconfiglib

def main():
    kconf = kconfiglib.standard_kconfig()

    # Avoid warnings printed by Kconfiglib when assigning a value to a symbol that
    # has no prompt. Such assignments never have an effect.
    kconf.disable_warnings()

    # Small optimization
    BOOL_TRI = (kconfiglib.BOOL, kconfiglib.TRISTATE)

    for sym in kconf.defined_syms:
        if sym.orig_type in BOOL_TRI:
            sym.set_value(2 if sym.is_allnoconfig_y else 0)

    kconf.write_config(kconfiglib.standard_config_filename())

if __name__ == "__main__":
    main()
