# Works like allnoconfig. Automatically verified by the testsuite to generate
# identical output to 'make allnoconfig' for all ARCHes. The looping is done in
# case setting one symbol to "n" allows other symbols to be set to "n" (due to
# dependencies).

import kconfiglib
import sys

conf = kconfiglib.Config(sys.argv[1])

# Do an initial pass to give allnoconfig_y symbols the user value 'y'. It might
# be possible to handle this through "successive raising" similarly to the
# "successive lowering" below too, but keep it simple.
for sym in conf:
    if sym.get_type() in (kconfiglib.BOOL, kconfiglib.TRISTATE) and \
       sym.is_allnoconfig_y():
        sym.set_user_value('y')

done = False
while not done:
    done = True

    for sym in conf:
        # Choices take care of themselves for allnoconfig, so we only need to
        # worry about non-choice symbols
        if not sym.is_choice_symbol() and not sym.is_allnoconfig_y():
            # If we can assign a value to the symbol (where "n", "m" and "y"
            # are ordered from lowest to highest), then assign the lowest
            # value. lower_bound() returns None for symbols whose values cannot
            # (currently) be changed, as well as for non-bool/tristate symbols.
            lower_bound = sym.get_lower_bound()
            if lower_bound is not None and \
               kconfiglib.tri_less(lower_bound, sym.get_value()):

                sym.set_user_value(lower_bound)
                # We just changed the value of some symbol. As this may affect
                # other symbols, keep going.
                done = False

conf.write_config(".config")
