# Shows a list of all (set) environment variables referenced in the Kconfig
# files, together with their values.
#
# Note: This only works for environment variables referenced via the $(FOO)
# preprocessor syntax. The older $FOO syntax is maintained for backwards
# compatibility.

import os
import sys

import kconfiglib


for var in kconfiglib.Kconfig(sys.argv[1]).env_vars:
    print("{:16} '{}'".format(var, os.environ[var]))
