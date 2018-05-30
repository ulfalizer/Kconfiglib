#!/usr/bin/env python

# Works like 'make alldefconfig'. Verified by the test suite to generate
# identical output to 'make alldefconfig' for all ARCHes.
#
# Usage for the Linux kernel:
#
#   $ make [ARCH=<arch>] scriptconfig SCRIPT=Kconfiglib/alldefconfig.py

import kconfiglib

def main():
    kconfiglib.standard_kconfig().write_config(
        kconfiglib.standard_config_filename())

if __name__ == "__main__":
    main()
