# This is a test suite for Kconfiglib. It runs selftests on Kconfigs provided
# by us and tests compatibility with the C Kconfig implementation by comparing
# the output of Kconfiglib with the output of the scripts/kconfig/*conf
# utilities for different targets and defconfigs. It should be run from the
# top-level kernel directory with
#
#  $ python Kconfiglib/kconfigtest.py
#
# Some additional options can be turned on by passing arguments. With no argument,
# they default to off.
#
#  - speedy:
#    Run scripts/kconfig/conf directly when comparing outputs instead of using
#    'make' targets. Makes things a lot faster, but could break if Kconfig
#    files start depending on additional environment variables besides ARCH and
#    SRCARCH. (These would be set in the Makefiles in that case.) Safe as of
#    Linux 3.7.0-rc8.
#
#  - obsessive:
#    By default, only valid arch/defconfig pairs will be tested. With this
#    enabled, every arch will be tested with every defconfig, which increases
#    the test time by an order of magnitude. Occassionally finds (usually very
#    obscure) bugs, and I make sure everything passes with it.
#
#  - log:
#    Log timestamped failures of the defconfig test to test_defconfig_fails in
#    the root. Especially handy in obsessive mode.
#
# For example, to run in speedy mode with logging, run
#
#  $ python Kconfiglib/kconfigtest.py speedy log
#
# (PyPy also works, and runs the defconfig tests roughly 20% faster on my
# machine. Some of the other tests get an even greater speed-up.)
#
# The tests have been roughly arranged in order of time needed.
#
# All tests should pass. Report regressions to kconfiglib@gmail.com

import kconfiglib
import os
import re
import subprocess
import sys
import textwrap
import time

speedy_mode = False
obsessive_mode = False
log_mode = False

# Assign this to avoid warnings from Kconfiglib. Nothing in the kernel's
# Kconfig files seems to actually look at the value as of 3.7.0-rc8. This is
# only relevant for the test suite, as this will get set by the kernel Makefile
# when using (i)scriptconfig.
os.environ["KERNELVERSION"] = "3.7.0"

# Prevent accidental loading of configuration files by removing
# KCONFIG_ALLCONFIG from the environment
os.environ.pop("KCONFIG_ALLCONFIG", None)

# Number of arch/defconfig pairs tested so far
nconfigs = 0

def run_tests():
    global speedy_mode, obsessive_mode, log_mode
    for s in sys.argv[1:]:
        if s == "speedy":
            speedy_mode = True
            print "Speedy mode enabled"
        elif s == "obsessive":
            obsessive_mode = True
            print "Obsessive mode enabled"
        elif s == "log":
            log_mode = True
            print "Log mode enabled"
        else:
            print "Unrecognized option '{0}'".format(s)
            return

    run_selftests()
    run_compatibility_tests()

def run_selftests():
    """Runs tests on specific configurations provided by us."""

    print "Running selftests...\n"

    print "Testing is_modifiable() and range queries..."

    #
    # is_modifiable()
    #

    c = kconfiglib.Config("Kconfiglib/tests/Kmodifiable")

    for s in ("VISIBLE", "TRISTATE_SELECTED_TO_M", "VISIBLE_STRING",
              "VISIBLE_INT", "VISIBLE_HEX"):
        verify(c[s].is_modifiable(),
               "{0} should be modifiable".format(c[s].get_name()))
    for s in ("NOT_VISIBLE", "SELECTED_TO_Y", "BOOL_SELECTED_TO_M",
              "M_VISIBLE_TRISTATE_SELECTED_TO_M", "NOT_VISIBLE_STRING",
              "NOT_VISIBLE_INT", "NOT_VISIBLE_HEX"):
        verify(not c[s].is_modifiable(),
               "{0} should not be modifiable".format(c[s].get_name()))

    #
    # get_lower/upper_bound() and get_assignable_values()
    #

    c = kconfiglib.Config("Kconfiglib/tests/Kbounds")

    def verify_bounds(sym_name, low, high):
        sym = c[sym_name]
        sym_low = sym.get_lower_bound()
        sym_high = sym.get_upper_bound()
        verify(sym_low == low and sym_high == high,
               "Incorrectly calculated bounds for {0}: {1}-{2}. "
               "Expected {3}-{4}.".format(sym.get_name(),
                                          sym_low, sym_high, low, high))
        # See that we get back the corresponding range from
        # get_assignable_values()
        if sym_low is None:
            vals = sym.get_assignable_values()
            verify(vals == [],
                   "get_assignable_values() thinks there should be assignable "
                   "values for {0} ({1}) but not get_lower/upper_bound()".
                   format(sym.get_name(), vals))
            if sym.get_type() in (kconfiglib.BOOL, kconfiglib.TRISTATE):
                verify(not sym.is_modifiable(),
                       "get_lower_bound() thinks there should be no "
                       "assignable values for the bool/tristate {0} but "
                       "is_modifiable() thinks it should be modifiable".
                       format(sym.get_name(), vals))
        else:
            tri_to_int = { "n" : 0, "m" : 1, "y" : 2 }
            bound_range = ["n", "m", "y"][tri_to_int[sym_low] :
                                          tri_to_int[sym_high] + 1]
            assignable_range = sym.get_assignable_values()
            verify(bound_range == assignable_range,
                   "get_lower/upper_bound() thinks the range for {0} should "
                   "be {1} while get_assignable_values() thinks it should be "
                   "{2}".format(sym.get_name(), bound_range, assignable_range))
            if sym.get_type() in (kconfiglib.BOOL, kconfiglib.TRISTATE):
                verify(sym.is_modifiable(),
                       "get_lower/upper_bound() thinks the range for the "
                       "bool/tristate{0} should be {1} while is_modifiable() "
                       "thinks the symbol should not be modifiable".
                       format(sym.get_name(), bound_range))

    verify_bounds("Y_VISIBLE_BOOL", "n", "y")
    verify_bounds("Y_VISIBLE_TRISTATE", "n", "y")
    verify_bounds("M_VISIBLE_BOOL", "n", "y")
    verify_bounds("M_VISIBLE_TRISTATE", "n", "m")
    verify_bounds("Y_SELECTED_BOOL", None, None)
    verify_bounds("M_SELECTED_BOOL", None, None)
    verify_bounds("Y_SELECTED_TRISTATE", None, None)
    verify_bounds("M_SELECTED_TRISTATE", "m", "y")
    verify_bounds("M_SELECTED_M_VISIBLE_TRISTATE", None, None)
    verify_bounds("STRING", None, None)
    verify_bounds("INT", None, None)
    verify_bounds("HEX", None, None)

    #
    # eval() (Already well exercised. Just test some basics.)
    #

    # TODO: Stricter syntax checking?

    print "Testing eval()..."

    c = kconfiglib.Config("Kconfiglib/tests/Keval")

    def verify_val(expr, val):
        res = c.eval(expr)
        verify(res == val,
               "'{0}' evaluated to {1}, expected {2}".format(expr, res, val))

    # No modules
    verify_val("n", "n")
    verify_val("m", "n")
    verify_val("y", "y")
    verify_val("'n'", "n")
    verify_val("'m'", "n")
    verify_val("'y'", "y")
    verify_val("M", "y")
    # Modules
    c["MODULES"].set_user_value("y")
    verify_val("n", "n")
    verify_val("m", "m")
    verify_val("y", "y")
    verify_val("'n'", "n")
    verify_val("'m'", "m")
    verify_val("'y'", "y")
    verify_val("M", "m")
    verify_val("(Y || N) && (m && y)", "m")

    # Non-bool/non-tristate symbols are always "n" in a tristate sense
    verify_val("Y_STRING", "n")
    verify_val("Y_STRING || m", "m")

    # As are all constants besides "y" and "m"
    verify_val('"foo"', "n")
    verify_val('"foo" || "bar"', "n")

    # Compare some constants...
    verify_val('"foo" != "bar"', "y")
    verify_val('"foo" = "bar"', "n")
    verify_val('"foo" = "foo"', "y")
    # As a quirk, undefined values get their name as their value
    c.set_print_warnings(False)
    verify_val("'not_defined' = not_defined", "y")
    verify_val("not_defined_2 = not_defined_2", "y")

    #
    # Text queries
    #

    # TODO: Get rid of extra \n's at end of texts?

    print "Testing text queries..."

    c = kconfiglib.Config("Kconfiglib/tests/Ktext")

    verify_equals(c["S"].get_name(), "S")
    verify_equals(c["NO_HELP"].get_help(), None)
    verify_equals(c["S"].get_help(), "help for\nS\n")
    verify_equals(c.get_choices()[0].get_help(), "help for\nC\n")
    verify_equals(c.get_comments()[0].get_text(), "a comment")
    verify_equals(c.get_menus()[0].get_title(), "a menu")

    #
    # Location queries
    #

    print "Testing location queries..."

    def verify_def_locations(sym_name, *locs):
        sym_locs = c[sym_name].get_def_locations()
        verify(len(sym_locs) == len(locs),
               "Wrong number of def. locations for " + sym_name)
        for i in range(0, len(sym_locs)):
            verify(sym_locs[i] == locs[i],
                   "Wrong def. location for {0}: Was {1}, should be {2}".
                   format(sym_name, sym_locs[i], locs[i]))

    # Expanded in the 'source' statement in Klocation
    os.environ["FOO"] = "tests"

    c = kconfiglib.Config("Kconfiglib/tests/Klocation", base_dir = "Kconfiglib/")

    verify_def_locations("A",
      ("Kconfiglib/tests/Klocation", 2),
      ("Kconfiglib/tests/Klocation", 21),
      ("Kconfiglib/tests/Klocation_included", 1),
      ("Kconfiglib/tests/Klocation_included", 3))
    verify_def_locations("C",
      ("Kconfiglib/tests/Klocation", 13))
    verify_def_locations("M",
      ("Kconfiglib/tests/Klocation_included", 6))
    verify_def_locations("N",
      ("Kconfiglib/tests/Klocation_included", 17))
    verify_def_locations("O",
      ("Kconfiglib/tests/Klocation_included", 19))
    verify_def_locations("NOT_DEFINED") # No locations

    def verify_ref_locations(sym_name, *locs):
        sym_locs = c[sym_name].get_ref_locations()
        verify(len(sym_locs) == len(locs),
               "Wrong number of ref. locations for " + sym_name)
        for i in range(0, len(sym_locs)):
            verify(sym_locs[i] == locs[i],
                   "Wrong ref. location for {0}: Was {1}, should be {2}".
                   format(sym_name, sym_locs[i], locs[i]))

    # Reload without the slash at the end of 'base_dir' to get coverage for
    # that as well
    c = kconfiglib.Config("Kconfiglib/tests/Klocation", base_dir = "Kconfiglib")

    verify_ref_locations("A",
      ("Kconfiglib/tests/Klocation", 6),
      ("Kconfiglib/tests/Klocation", 7),
      ("Kconfiglib/tests/Klocation", 11),
      ("Kconfiglib/tests/Klocation", 27),
      ("Kconfiglib/tests/Klocation", 28),
      ("Kconfiglib/tests/Klocation_included", 7),
      ("Kconfiglib/tests/Klocation_included", 8),
      ("Kconfiglib/tests/Klocation_included", 9),
      ("Kconfiglib/tests/Klocation_included", 12),
      ("Kconfiglib/tests/Klocation_included", 13),
      ("Kconfiglib/tests/Klocation_included", 33),
      ("Kconfiglib/tests/Klocation", 45),
      ("Kconfiglib/tests/Klocation", 46),
      ("Kconfiglib/tests/Klocation", 47))
    verify_ref_locations("C")
    verify_ref_locations("NOT_DEFINED",
      ("Kconfiglib/tests/Klocation", 7),
      ("Kconfiglib/tests/Klocation", 22),
      ("Kconfiglib/tests/Klocation_included", 12),
      ("Kconfiglib/tests/Klocation_included", 33))

    # Location queries for choices

    def verify_choice_locations(choice, *locs):
        choice_locs = choice.get_def_locations()
        verify(len(choice_locs) == len(locs),
               "Wrong number of def. locations for choice")
        for i in range(0, len(choice_locs)):
            verify(choice_locs[i] == locs[i],
                   "Wrong def. location for choice: Was {0}, should be {1}".
                   format(choice_locs[i], locs[i]))

    choice_1, choice_2 = c.get_choices()

    # Throw in named choice test
    verify(choice_1.get_name() == "B",
           "The first choice should be called B")
    verify(choice_2.get_name() is None,
           "The second choice should have no name")

    verify_choice_locations(choice_1,
      ("Kconfiglib/tests/Klocation", 10),
      ("Kconfiglib/tests/Klocation_included", 22))
    verify_choice_locations(choice_2,
      ("Kconfiglib/tests/Klocation_included", 15))

    # Location queries for menus and comments

    def verify_location(menu_or_comment, loc):
        menu_or_comment_loc = menu_or_comment.get_location()
        verify(menu_or_comment_loc == loc,
               "Wrong location for {0} with text '{1}': Was {2}, should be "
               "{3}".format("menu" if menu_or_comment.is_menu() else "comment",
                            menu_or_comment.get_title() if
                              menu_or_comment.is_menu() else
                              menu_or_comment.get_text(),
                            menu_or_comment_loc,
                            loc))

    menu_1, menu_2 = c.get_menus()
    comment_1, comment_2 = c.get_comments()

    verify_location(menu_1, ("Kconfiglib/tests/Klocation", 5))
    verify_location(menu_2, ("Kconfiglib/tests/Klocation_included", 5))
    verify_location(comment_1, ("Kconfiglib/tests/Klocation", 24))
    verify_location(comment_2, ("Kconfiglib/tests/Klocation_included", 34))

    #
    # Object relations
    #

    c = kconfiglib.Config("Kconfiglib/tests/Krelation")

    A, B, C, D, E, F, G, H, I = c["A"], c["B"], c["C"], c["D"], c["E"], c["F"],\
                                c["G"], c["H"], c["I"]
    choice_1, choice_2 = c.get_choices()
    verify([menu.get_title() for menu in c.get_menus()] ==
           ["m1", "m2", "m3", "m4"],
           "menu ordering is broken")
    menu_1, menu_2, menu_3, menu_4 = c.get_menus()

    print "Testing object relations..."

    verify(A.get_parent() is None, "A should not have a parent")
    verify(B.get_parent() is choice_1, "B's parent should be the first choice")
    verify(E.get_parent() is menu_1, "E's parent should be the first menu")
    verify(E.get_parent().get_parent() is None,
           "E's grandparent should be None")
    verify(G.get_parent() is choice_2,
           "G's parent should be the second choice")
    verify(G.get_parent().get_parent() is menu_2,
           "G's grandparent should be the second menu")

    #
    # Object fetching (same test file)
    #

    print "Testing object fetching..."

    verify_equals(c.get_symbol("NON_EXISTENT"), None)
    verify(c.get_symbol("A") is A, "get_symbol() is broken")

    verify(c.get_top_level_items() == [A, choice_1, menu_1, menu_3, menu_4],
           "Wrong items at top level")
    verify(c.get_symbols(False) == [A, B, C, D, E, F, G, H, I],
           "get_symbols() is broken")

    verify(choice_1.get_items() == [B, C, D],
           "Wrong get_items() items in 'choice'")
    # Test Kconfig quirk
    verify(choice_1.get_actual_items() == [B, D],
           "Wrong get_actual_items() items in 'choice'")

    verify(menu_1.get_items() == [E, menu_2, I], "Wrong items in first menu")
    verify(menu_1.get_symbols() == [E, I], "Wrong symbols in first menu")
    verify(menu_1.get_items(True) == [E, menu_2, F, choice_2, G, H, I],
           "Wrong recursive items in first menu")
    verify(menu_1.get_symbols(True) == [E, F, G, H, I],
           "Wrong recursive symbols in first menu")
    verify(menu_2.get_items() == [F, choice_2],
           "Wrong items in second menu")
    verify(menu_2.get_symbols() == [F],
           "Wrong symbols in second menu")
    verify(menu_2.get_items(True) == [F, choice_2, G, H],
           "Wrong recursive items in second menu")
    verify(menu_2.get_symbols(True) == [F, G, H],
           "Wrong recursive symbols in second menu")

    #
    # get_referenced_symbols()
    #

    c = kconfiglib.Config("Kconfiglib/tests/Kref")

    # General function for checking get_referenced_symbols() output.
    # Specialized for symbols below.
    def verify_refs(item, refs_no_enclosing, refs_enclosing):
        item_refs = item.get_referenced_symbols()
        item_refs_enclosing = item.get_referenced_symbols(True)

        # For failure messages
        if item.is_symbol():
            item_string = item.get_name()
        elif item.is_choice():
            if item.get_name() is None:
                item_string = "choice"
            else:
                item_string = "choice " + item.get_name()
        elif item.is_menu():
            item_string = 'menu "{0}"'.format(item.get_title())
        else:
            # Comment
            item_string = 'comment "{0}"'.format(item.get_text())

        verify(len(item_refs) == len(refs_no_enclosing),
               "Wrong number of refs excluding enclosing for {0}".
               format(item_string))
        verify(len(item_refs_enclosing) == len(refs_enclosing),
               "Wrong number of refs including enclosing for {0}".
               format(item_string))
        for r in [c[name] for name in refs_no_enclosing]:
            verify(r in item_refs,
                   "{0} should reference {1} when excluding enclosing".
                   format(item_string, r.get_name()))
        for r in [c[name] for name in refs_enclosing]:
            verify(r in item_refs_enclosing,
                   "{0} should reference {1} when including enclosing".
                   format(item_string, r.get_name()))

    # Symbols referenced by symbols

    def verify_sym_refs(sym_name, refs_no_enclosing, refs_enclosing):
        verify_refs(c[sym_name], refs_no_enclosing, refs_enclosing)

    verify_sym_refs("NO_REF", [], [])
    verify_sym_refs("ONE_REF", ["A"], ["A"])
    own_refs = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L",
                "M", "N", "O"]
    verify_sym_refs("MANY_REF",
      own_refs,
      own_refs + ["IF_REF_1", "IF_REF_2", "MENU_REF_1",
                  "MENU_REF_2"])

    # Symbols referenced by choices

    own_refs = ["CHOICE_REF_4", "CHOICE_REF_5", "CHOICE_REF_6"]
    verify_refs(c.get_choices()[0],
      own_refs,
      own_refs + ["CHOICE_REF_1", "CHOICE_REF_2", "CHOICE_REF_3"])

    # Symbols referenced by menus

    own_refs = ["NO_REF", "MENU_REF_3"]
    verify_refs(c.get_menus()[1],
      own_refs,
      own_refs + ["MENU_REF_1", "MENU_REF_2"])

    # Symbols referenced by comments

    own_refs = ["COMMENT_REF_3", "COMMENT_REF_4", "COMMENT_REF_5"]
    verify_refs(c.get_comments()[0],
      own_refs,
      own_refs + ["COMMENT_REF_1", "COMMENT_REF_2"])

    #
    # get_selected_symbols() (same test file)
    #

    def verify_selects(sym_name, selection_names):
        sym = c[sym_name]
        sym_selections = sym.get_selected_symbols()
        verify(len(sym_selections) == len(selection_names),
               "Wrong number of selects for {0}".format(sym.get_name()))
        for s in [c[name] for name in selection_names]:
            verify(s in sym_selections, "{0} should be selected by {1}".
                                        format(s.get_name(), sym.get_name()))

    verify_selects("NO_REF", [])
    verify_selects("MANY_REF", ["I", "N"])

    #
    # get_defconfig_filename()
    #

    print "Testing get_defconfig_filename()..."

    c = kconfiglib.Config("Kconfiglib/tests/Kdefconfig_none")
    verify(c.get_defconfig_filename() is None,
           "get_defconfig_filename() should be None with no defconfig_list "
           "symbol")

    c = kconfiglib.Config("Kconfiglib/tests/Kdefconfig_nonexistent")
    verify(c.get_defconfig_filename() is None,
           "get_defconfig_filename() should be None when none of the files "
           "in the defconfig_list symbol exist")

    # Referenced in Kdefconfig_existent(_but_n)
    os.environ["BAR"] = "defconfig_2"

    c = kconfiglib.Config("Kconfiglib/tests/Kdefconfig_existent_but_n")
    verify(c.get_defconfig_filename() is None,
           "get_defconfig_filename() should be None when the condition is "
           "n for all the defaults")

    c = kconfiglib.Config("Kconfiglib/tests/Kdefconfig_existent")
    verify(c.get_defconfig_filename() == "Kconfiglib/tests/defconfig_2",
           "get_defconfig_filename() should return the existent file "
           "Kconfiglib/tests/defconfig_2")

    #
    # Misc. minor APIs
    #

    c = kconfiglib.Config("Kconfiglib/tests/Kmisc")

    print "Testing is_optional()..."

    verify(not c.get_choices()[0].is_optional(),
           "First choice should not be optional")
    verify(c.get_choices()[1].is_optional(),
           "Second choice should be optional")

    print "Testing get_user_value()..."

    # Avoid warnings from assigning invalid user values and assigning user
    # values to symbols without prompts
    c.set_print_warnings(False)

    syms = [c[name] for name in \
      ("BOOL", "TRISTATE", "STRING", "INT", "HEX")]
    b, t, s, i, h = syms

    for sym in syms:
        verify(sym.get_user_value() is None,
               "{0} should not have a user value to begin with")

    def assign_and_verify_new_user_value(sym, val, new_val):
        old_val = sym.get_user_value()
        sym.set_user_value(val)
        verify(sym.get_user_value() == new_val,
               "{0} should have the value {1} after being assigned {2}. "
               "The old value was {3}.".
               format(sym.get_name(), new_val, val, old_val))

    # Assign valid values for the types

    assign_and_verify_new_user_value(b, "n", "n")
    assign_and_verify_new_user_value(b, "y", "y")
    assign_and_verify_new_user_value(t, "n", "n")
    assign_and_verify_new_user_value(t, "m", "m")
    assign_and_verify_new_user_value(t, "y", "y")
    assign_and_verify_new_user_value(s, "foo bar", "foo bar")
    assign_and_verify_new_user_value(i, "123", "123")
    assign_and_verify_new_user_value(h, "0x123", "0x123")

    # Assign invalid values for the types. They should retain their old user
    # value.

    assign_and_verify_new_user_value(b, "m", "y")
    assign_and_verify_new_user_value(b, "foo", "y")
    assign_and_verify_new_user_value(b, "1", "y")
    assign_and_verify_new_user_value(t, "foo", "y")
    assign_and_verify_new_user_value(t, "1", "y")
    assign_and_verify_new_user_value(i, "foo", "123")
    assign_and_verify_new_user_value(h, "foo", "0x123")

    for s in syms:
        s.unset_user_value()
        verify(s.get_user_value() is None,
               "{0} should not have a user value after being reset".
               format(s.get_name()))

    #
    # Object dependencies
    #

    print "Testing object dependencies..."

    # Note: This tests an internal API

    c = kconfiglib.Config("Kconfiglib/tests/Kdep")

    def verify_dependent(sym_name, deps_names):
        sym = c[sym_name]
        deps = [c[name] for name in deps_names]
        sym_deps = sym._get_dependent()
        verify(len(sym_deps) == len(deps),
               "Wrong number of dependent symbols for {0}".
               format(sym.get_name()))
        verify(len(sym_deps) == len(set(sym_deps)),
               "{0}'s dependencies contains duplicates".
               format(sym.get_name()))
        for dep in deps:
            verify(dep in sym_deps, "{0} should depend on {1}".
                                    format(dep.get_name(), sym.get_name()))

    # Test twice to cover dependency caching
    for i in range(0, 2):
        n_deps = 28
        # Verify that D1, D2, .., D<n_deps> are dependent on D
        verify_dependent("D", ["D{0}".format(i) for i in range(1, n_deps + 1)])
        # Choices
        verify_dependent("A", ["B", "C"])
        verify_dependent("B", ["A", "C"])
        verify_dependent("C", ["A", "B"])
        verify_dependent("S", ["A", "B", "C"])

    print
    if _all_ok:
        print "All selftests passed"
    else:
        print "Some selftests failed"
    print

def run_compatibility_tests():
    """Runs tests on configurations from the kernel. Tests compability with the
    C implementation by comparing outputs."""

    print "Running compatibility tests...\n"

    # The set of tests that want to run for all architectures in the kernel
    # tree -- currently, all tests. The boolean flag indicates whether .config
    # (generated by the C implementation) should be compared to ._config
    # (generated by us) after each invocation.
    all_arch_tests = [(test_config_absent,  True),
                      (test_call_all,       False),
                      (test_all_no,         True),
                      (test_all_yes,        True),
                      (test_all_no_simpler, True),
                      # Needs to report success/failure for each arch/defconfig
                      # combo, hence False.
                      (test_defconfig,      False)]

    print "Loading Config instances for all architectures..."
    arch_configs = get_arch_configs()

    for (test_fn, compare_configs) in all_arch_tests:
        print "\nUnsetting user values on all architecture Config instances "\
              "prior to next test..."
        for arch in arch_configs:
            arch.unset_user_values()

        # The test description is taken from the docstring of the corresponding
        # function
        print textwrap.dedent(test_fn.__doc__)

        for conf in arch_configs:
            rm_configs()

            # This should be set correctly for any 'make *config' commands the
            # test might run. SRCARCH is selected automatically from ARCH, so
            # we don't need to set that.
            os.environ["ARCH"] = conf.get_arch()
            # This won't get set for us in speedy mode
            if speedy_mode:
                os.environ["SRCARCH"] = conf.get_srcarch()

            test_fn(conf)

            if compare_configs:
                sys.stdout.write("  {0:<14}".format(conf.get_arch()))

                if equal_confs():
                    print "OK"
                else:
                    print "FAIL"
                    fail()

    if all_ok():
        print "All selftests and compatibility tests passed"
        print nconfigs, "arch/defconfig pairs tested"
    else:
        print "Some tests failed"

def get_arch_configs():
    """Returns a list with Config instances corresponding to all arch
    Kconfigs."""

    # TODO: Could this be made more robust across kernel versions by checking
    # for the existence of particular arches?

    def add_arch(ARCH, res):
        os.environ["SRCARCH"] = archdir
        os.environ["ARCH"] = ARCH
        c = kconfiglib.Config(base_dir = ".")
        res.append(c)
        print "  Loaded " + c.get_arch()

    res = []

    for archdir in os.listdir("arch"):
        # No longer broken as of 3.7.0-rc8
        #if archdir == "h8300":
            # Broken Kconfig as of Linux 2.6.38-rc3
            #continue

        if os.path.exists(os.path.join("arch", archdir, "Kconfig")):
            add_arch(archdir, res)
            # Some arches define additional ARCH settings with ARCH != SRCARCH.
            # (Search for "Additional ARCH settings for" in the Makefile.) We
            # test those as well.
            if archdir == "x86":
                add_arch("i386", res)
                add_arch("x86_64", res)
            elif archdir == "sparc":
                add_arch("sparc32", res)
                add_arch("sparc64", res)
            elif archdir == "sh":
                add_arch("sh64", res)
            elif archdir == "tile":
                add_arch("tilepro", res)
                add_arch("tilegx", res)

    # Don't want subsequent 'make *config' commands in tests to see this
    del os.environ["ARCH"]
    del os.environ["SRCARCH"]

    return res

# The weird docstring formatting is to get the format right when we print the
# docstring ourselves
def test_all_no(conf):
    """
    Test if our examples/allnoconfig.py script generates the same .config as
    'make allnoconfig' for each architecture. Runs the script via
    'make scriptconfig' and needs to reparse the configurations, so kinda slow
    even in speedy mode."""

    # TODO: Support speedy mode for running the script
    shell("make scriptconfig SCRIPT=Kconfiglib/examples/allnoconfig.py")
    shell("mv .config ._config")
    if speedy_mode:
        shell("scripts/kconfig/conf --allnoconfig Kconfig")
    else:
        shell("make allnoconfig")

def test_all_no_simpler(conf):
    """
    Test if our examples/allnoconfig_simpler.py script generates the same
    .config as 'make allnoconfig' for each architecture. Runs the script via
    'make scriptconfig' and needs to reparse the configurations, so kinda slow
    even in speedy mode."""

    # TODO: Support speedy mode for running the script
    shell("make scriptconfig SCRIPT=Kconfiglib/examples/allnoconfig_simpler.py")
    shell("mv .config ._config")
    if speedy_mode:
        shell("scripts/kconfig/conf --allnoconfig Kconfig")
    else:
        shell("make allnoconfig")

def test_all_yes(conf):
    """
    Test if our examples/allyesconfig.py script generates the same .config as
    'make allyesconfig' for each architecture. Runs the script via
    'make scriptconfig' and needs to reparse the configurations, so kinda slow
    even in speedy mode."""

    # TODO: Support speedy mode for running the script
    shell("make scriptconfig SCRIPT=Kconfiglib/examples/allyesconfig.py")
    shell("mv .config ._config")
    if speedy_mode:
        shell("scripts/kconfig/conf --allyesconfig Kconfig")
    else:
        shell("make allyesconfig")

def test_call_all(conf):
    """
    Call all public methods on all symbols, menus, choices and comments (nearly
    all public methods: some are hard to test like this, but are exercised by
    other tests) for all architectures to make sure we never crash or hang.
    Also do misc. sanity checks."""
    print "  For {0}...".format(conf.get_arch())

    conf.get_arch()
    conf.get_srcarch()
    conf.get_srctree()
    conf.get_config_filename()
    conf.get_defconfig_filename()
    conf.get_top_level_items()
    conf.eval("y && ARCH")

    # Syntax error
    caught_exception = False
    try:
        conf.eval("y && && y")
    except kconfiglib.Kconfig_Syntax_Error:
        caught_exception = True

    verify(caught_exception,
           "No exception generated for expression with syntax error")

    conf.get_config_header()
    conf.get_base_dir()
    conf.unset_user_values()
    conf.get_symbols(False)
    conf.get_mainmenu_text()

    for s in conf.get_symbols():
        s.unset_user_value()
        s.get_value()
        s.get_user_value()
        s.get_name()
        s.get_upper_bound()
        s.get_lower_bound()
        s.get_assignable_values()
        s.get_type()
        s.get_visibility()
        s.get_parent()
        s.get_referenced_symbols()
        s.get_referenced_symbols(True)
        s.get_selected_symbols()
        s.get_help()
        s.get_config()

        # Check get_ref/def_location() sanity

        if s.is_special():
            if s.is_from_environment():
                # Special symbols from the environment should have define
                # locations
                verify(s.get_def_locations() != [],
                       "The symbol '{0}' is from the environment but lacks "
                       "define locations".format(s.get_name()))
            else:
                # Special symbols that are not from the environment should be
                # defined and have no define locations
                verify(s.is_defined(),
                       "The special symbol '{0}' is not defined".
                       format(s.get_name()))
                verify(s.get_def_locations() == [],
                       "The special symbol '{0}' has recorded def. locations".
                       format(s.get_name()))
        else:
            # Non-special symbols should have define locations iff they are
            # defined
            if s.is_defined():
                verify(s.get_def_locations() != [],
                       "'{0}' defined but lacks recorded locations".
                       format(s.get_name()))
            else:
                verify(s.get_def_locations() == [],
                       "'{0}' undefined but has recorded locations".
                       format(s.get_name()))
                verify(s.get_ref_locations() != [],
                       "'{0}' both undefined and unreferenced".
                       format(s.get_name()))

        s.get_ref_locations()
        s.is_modifiable()
        s.is_defined()
        s.is_from_environment()
        s.has_ranges()
        s.is_choice_item()
        s.is_choice_selection()
        s.__str__()

    for c in conf.get_choices():
        c.get_name()
        c.get_selection()
        c.get_selection_from_defaults()
        c.get_user_selection()
        c.get_type()
        c.get_name()
        c.get_items()
        c.get_actual_items()
        c.get_parent()
        c.get_referenced_symbols()
        c.get_referenced_symbols(True)
        c.get_def_locations()
        c.get_visibility()
        c.get_mode()
        c.is_optional()
        c.__str__()

    for m in conf.get_menus():
        m.get_items()
        m.get_symbols(False)
        m.get_symbols(True)
        m.get_depends_on_visibility()
        m.get_visible_if_visibility()
        m.get_title()
        m.get_parent()
        m.get_referenced_symbols()
        m.get_referenced_symbols(True)
        m.get_location()
        m.__str__()

    for c in conf.get_comments():
        c.get_text()
        c.get_parent()
        c.get_referenced_symbols()
        c.get_referenced_symbols(True)
        c.get_location()
        c.__str__()

def test_config_absent(conf):
    """
    Test if kconfiglib generates the same configuration as 'make alldefconfig'
    for each architecture."""
    conf.write_config("._config")
    if speedy_mode:
        shell("scripts/kconfig/conf --alldefconfig Kconfig")
    else:
        shell("make alldefconfig")

def test_defconfig(conf):
    """
    Test if kconfiglib generates the same .config as scripts/kconfig/conf for
    each architecture/defconfig pair. In obsessive mode, this test includes
    nonsensical groupings of arches with defconfigs from other arches (every
    arch/defconfig combination) and an order of magnitude longer time to run.

    With logging enabled, this test appends any failures to a file
    test_defconfig_fails in the root."""

    global nconfigs
    defconfigs = []

    def add_configs_for_arch(arch):
        arch_dir = os.path.join("arch", arch)
        # Some arches have a "defconfig" in the root of their arch/<arch>/
        # directory
        root_defconfig = os.path.join(arch_dir, "defconfig")
        if os.path.exists(root_defconfig):
            defconfigs.append(root_defconfig)
        # Assume all files in the arch/<arch>/configs directory (if it
        # exists) are configurations
        defconfigs_dir = os.path.join(arch_dir, "configs")
        if not os.path.exists(defconfigs_dir):
            return
        if not os.path.isdir(defconfigs_dir):
            print "Warning: '{0}' is not a directory - skipping"\
                  .format(defconfigs_dir)
            return
        for dirpath, dirnames, filenames in os.walk(defconfigs_dir):
            for filename in filenames:
                defconfigs.append(os.path.join(dirpath, filename))

    if obsessive_mode:
        # Collect all defconfigs. This could be done once instead, but it's
        # a speedy operation comparatively.
        for arch in os.listdir("arch"):
            add_configs_for_arch(arch)
    else:
        add_configs_for_arch(conf.get_arch())

    # Test architecture for each defconfig

    for defconfig in defconfigs:
        rm_configs()

        nconfigs += 1

        conf.load_config(defconfig)
        conf.write_config("._config")
        if speedy_mode:
            shell("scripts/kconfig/conf --defconfig='{0}' Kconfig".
                  format(defconfig))
        else:
            shell("cp {0} .config".format(defconfig))
            # It would be a bit neater if we could use 'make *_defconfig'
            # here (for example, 'make i386_defconfig' loads
            # arch/x86/configs/i386_defconfig' if ARCH = x86/i386/x86_64),
            # but that wouldn't let us test nonsensical combinations of
            # arches and defconfigs, which is a nice way to find obscure
            # bugs.
            shell("make kconfiglibtestconfig")

        sys.stdout.write("  {0:<14}with {1:<60} ".
                         format(conf.get_arch(), defconfig))

        if equal_confs():
            print "OK"
        else:
            print "FAIL"
            fail()
            if log_mode:
                with open("test_defconfig_fails", "a") as fail_log:
                    fail_log.write("{0}  {1} with {2} did not match\n"
                            .format(time.strftime("%d %b %Y %H:%M:%S",
                                                  time.localtime()),
                                    conf.get_arch(),
                                    defconfig))

#
# Helper functions
#

devnull = open(os.devnull, "w")

def shell(cmd):
    subprocess.call(cmd, shell = True, stdout = devnull, stderr = devnull)

def rm_configs():
    """Delete any old ".config" (generated by the C implementation) and
    "._config" (generated by us), if present."""
    def rm_if_exists(f):
        if os.path.exists(f):
            os.remove(f)

    rm_if_exists(".config")
    rm_if_exists("._config")

def equal_confs():
    with open(".config") as menu_conf:
        l1 = menu_conf.readlines()

    with open("._config") as my_conf:
        l2 = my_conf.readlines()

    # Skip the header generated by 'conf'
    unset_re = r"# CONFIG_(\w+) is not set"
    i = 0
    for line in l1:
        if not line.startswith("#") or \
           re.match(unset_re, line):
            break
        i += 1

    return (l1[i:] == l2)

_all_ok = True

def verify(cond, msg):
    """Fails and prints 'msg' if 'conf' is False."""
    if not cond:
        fail(msg)

def verify_equals(x, y):
    """Fails if 'x' does not equal 'y'."""
    if x != y:
        fail("'{0}' does not equal '{1}'".format(x, y))

def fail(msg = None):
    global _all_ok
    if msg is not None:
        print "Fail: " + msg
    _all_ok = False

def all_ok():
    return _all_ok

if __name__ == "__main__":
    run_tests()
