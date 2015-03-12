# This is a simpler version of allnoconfig.py, corresponding to how the C
# implementation does it. Setting a user value that's not in the assignable
# range of the symbol (between get_lower_bound() and get_upper_bound(), or,
# equivalently, not in get_assignable_values()) is OK; the value will simply
# get truncated downwards or upwards as determined by the visibility and
# selects.

# This version is a bit slower compared allnoconfig.py since Kconfiglib
# invalidates all dependent symbols for each set_user_value() call. This does not
# happen for load_config(), which instead invalidates all symbols once after
# the configuration has been loaded. This is OK for load_config() since nearly
# all symbols will tend to be affected anyway.

import kconfiglib
import sys

conf = kconfiglib.Config(sys.argv[1])

# Avoid warnings printed by Kconfiglib when assigning a user value with
# set_user_value() to a symbol that has no prompt (such assignments never have
# an effect)
conf.set_print_warnings(False)

for sym in conf:
    if sym.get_type() in (kconfiglib.BOOL, kconfiglib.TRISTATE):
        sym.set_user_value("y" if sym.is_allnoconfig_y() else "n")

conf.write_config(".config")
