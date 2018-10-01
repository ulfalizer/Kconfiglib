#!/usr/bin/env python

# Copyright (c) 2018, Ulf Magnusson
# SPDX-License-Identifier: ISC

# Works like 'make olddefconfig', updating an old .config file by filing in
# default values for all new symbols. This is the same as picking the default
# selection for all symbols in oldconfig, or entering the menuconfig interface
# and immediately saving.
#
# The default output filename is '.config'. A different filename can be passed
# in the KCONFIG_CONFIG environment variable.

import os
import sys

import kconfiglib


def main():
    config_filename = kconfiglib.standard_config_filename()
    if not os.path.exists(config_filename):
        sys.exit("{}: '{}' not found".format(sys.argv[0], config_filename))

    kconf = kconfiglib.standard_kconfig()
    kconf.load_config(config_filename)
    kconf.write_config(config_filename)
    print("Updated configuration written to '{}'".format(config_filename))


if __name__ == "__main__":
    main()
