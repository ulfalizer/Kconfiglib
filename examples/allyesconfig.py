# Works like allyesconfig. This is a bit more involved than allnoconfig as we
# need to handle choices in two different modes:
#
# "y": One symbol is "y", the rest are "n".
# "m": Any number of symbols are "m", the rest are "n".
#
# Only tristate choices can be in "m" mode. It is safe since the code for two
# conflicting options will appear as separate modules instead of simultaneously
# in the kernel.
#
# If a choice can be in "y" mode, it will be. If it can only be in "m" mode
# (due to dependencies), then all the options will be set to "m".
#
# The looping is in case setting one symbol to "y" (or "m") allows the value of
# other symbols to be raised.

import kconfiglib
import sys

conf = kconfiglib.Config(sys.argv[1])

# Get a list of all symbols that are not in choices
non_choice_syms = [sym for sym in conf.get_symbols() if
                   not sym.is_choice_symbol()]

done = False
while not done:
    done = True

    # Handle symbols outside of choices

    for sym in non_choice_syms:
        upper_bound = sym.get_upper_bound()

        # See corresponding comment for allnoconfig implementation
        if upper_bound is not None and \
           kconfiglib.tri_less(sym.get_value(), upper_bound):
            sym.set_user_value(upper_bound)
            done = False

    # Handle symbols within choices

    for choice in conf.get_choices():

        # Handle choices whose visibility allow them to be in "y" mode

        if choice.get_visibility() == "y":
            selection = choice.get_selection_from_defaults()
            if selection is not None and \
               selection is not choice.get_user_selection():
                selection.set_user_value("y")
                done = False

        # Handle choices whose visibility only allow them to be in "m" mode.
        # This might happen if a choice depends on a symbol that can only be
        # "m" for example.

        elif choice.get_visibility() == "m":
            for sym in choice.get_symbols():
                if sym.get_value() != "m" and \
                   sym.get_upper_bound() != "n":
                    sym.set_user_value("m")
                    done = False

conf.write_config(".config")
