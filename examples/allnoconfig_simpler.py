# This is a simpler version of allnoconfig.py, corresponding to how the C
# implementation does it. Verified by the test suite to produce identical
# output to 'make allnoconfig' for all ARCHes.
#
# Usage:
#
#   $ make [ARCH=<arch>] scriptconfig SCRIPT=Kconfiglib/examples/allnoconfig_simpler.py

from kconfiglib import Kconfig, BOOL, TRISTATE
import sys

kconf = Kconfig(sys.argv[1])

# Avoid warnings printed by Kconfiglib when assigning a value to a symbol that
# has no prompt. Such assignments never have an effect.
kconf.disable_warnings()

for sym in kconf.defined_syms:
    if sym.type in (BOOL, TRISTATE):
        sym.set_value(2 if sym.is_allnoconfig_y else 0)

kconf.write_config(".config")
