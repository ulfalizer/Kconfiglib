# This is a simpler version of allnoconfig.py, corresponding to how the C
# implementation does it. Verified by the test suite to produce identical
# output to 'make allnoconfig' for all ARCHes.
#
# Usage:
#
#   $ make [ARCH=<arch>] scriptconfig SCRIPT=Kconfiglib/examples/allnoconfig_simpler.py
#
# Implementation/performance note
# ===============================
#
# Kconfiglib immediately invalidates (flags for recalculation) all (possibly)
# dependent symbols when a value is assigned to a symbol, which slows this down
# a bit (due to tons of redundant invalidation), but makes any assignment
# pattern safe ("just works"). Kconfig.load_config() instead invalidates all
# symbols up front, making it much faster. If you really need to eke out
# performance, look at how load_config() does things (which involves internal
# APIs that don't invalidate symbols). This has been fast enough for all cases
# I've seen so far though (around 3 seconds for this particular script on my
# Core i7 2600K, including the initial Kconfig parsing).

from kconfiglib import Kconfig, BOOL, TRISTATE
import sys

conf = Kconfig(sys.argv[1])

# Avoid warnings printed by Kconfiglib when assigning a value to a symbol that
# has no prompt. Such assignments never have an effect.
conf.disable_warnings()

for sym in conf.defined_syms:
    if sym.type in (BOOL, TRISTATE):
        sym.set_value(2 if sym.is_allnoconfig_y else 0)

conf.write_config(".config")
