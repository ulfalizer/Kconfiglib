#!/usr/bin/env python

# Copyright (c) 2018, Ulf Magnusson
# SPDX-License-Identifier: ISC

# Works like 'make allmodconfig'. Verified by the test suite to generate output
# identical to 'make allmodconfig', for all ARCHES.
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

    # Small optimizations
    BOOL = kconfiglib.BOOL
    TRISTATE = kconfiglib.TRISTATE

    for sym in kconf.defined_syms:
        if sym.orig_type == BOOL:
            # 'bool' choice symbols get their default value, as determined by
            # e.g. 'default's on the choice
            if not sym.choice:
                # All other bool symbols get set to 'y', like for allyesconfig
                sym.set_value(2)
        elif sym.orig_type == TRISTATE:
            sym.set_value(1)

    for choice in kconf.choices:
        choice.set_value(2 if choice.orig_type == BOOL else 1)

    kconf.write_config(kconfiglib.standard_config_filename())

if __name__ == "__main__":
    main()
