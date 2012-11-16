# This is a test suite for kconfiglib, primarily testing compatibility with the
# C kconfig implementation by comparing outputs. It should be run from the
# top-level kernel directory with
#
# $ PYTHONPATH=scripts/kconfig python scripts/kconfig/kconfigtest.py
#
# Note that running these could take a long time: running all tests on a Core
# i7@2.67 GHz takes ~2 hours. The tests have been arranged in order of time
# needed.
#
# All tests should pass. Report regressions to kconfiglib@gmail.com

import kconfiglib
import os
import re
import subprocess
import sys

# Assume that the value of KERNELVERSION does not affect the configuration
# (true as of Linux 2.6.38-rc3). Here we could fetch the correct version
# instead.
os.environ["KERNELVERSION"] = "2"

# Number of arch/defconfig pairs tested so far
nconfigs = 0

def run_tests():
    # The set of tests that want to run for all architectures in the kernel
    # tree -- currently, all tests. The boolean flag indicates whether .config
    # (generated by the C implementation) should be compared to ._config
    # (generated by us) after each invocation.
    all_arch_tests = [(test_all_no,        True),
                      (test_config_absent, True),
                      (test_all_yes,       True),
                      (test_call_all,      False),
                      # Needs to report success/failure for each arch/defconfig
                      # combo, hence False.
                      (test_defconfig,     False)]

    print "Loading Config instances for all architectures..."
    arch_configs = get_arch_configs()

    for (test_fn, compare_configs) in all_arch_tests:
        print "Resetting all architecture Config instances prior to next test..."
        for arch in arch_configs:
            arch.reset()

        # The test description is taken from the docstring of the corresponding
        # function
        print test_fn.__doc__

        for conf in arch_configs:
            rm_configs()

            # This should be set correctly for any 'make *config' commands the
            # test might run
            os.environ["ARCH"] = conf.get_arch()
            os.environ["SRCARCH"] = conf.get_srcarch()

            test_fn(conf)

            if compare_configs:
                sys.stdout.write("  {0:<14}".format(conf.get_arch()))

                if equal_confs():
                    print "OK"
                else:
                    print "FAIL"
                    fail()

        print ""

    if all_ok():
        print "All OK"
        print nconfigs, "arch/defconfig pairs tested"
    else:
        print "Some tests failed"

def get_arch_configs():
    """Returns a list with Config instances corresponding to all arch Kconfigs."""

    def add_arch(ARCH, res):
        os.environ["SRCARCH"] = archdir
        os.environ["ARCH"] = ARCH
        res.append(kconfiglib.Config(base_dir = "."))

    res = []

    # Nothing looks at this as of Linux 2.6.38-rc3
    os.environ["KERNELVERSION"] = "2"

    for archdir in os.listdir("arch"):
        if archdir == "h8300":
            # Broken Kconfig as of Linux 2.6.38-rc3
            continue

        if os.path.exists(os.path.join("arch", archdir, "Kconfig")):
            if archdir == "x86":
                add_arch("i386", res)
                add_arch("x86_64", res)
            elif archdir == "sparc":
                add_arch("sparc32", res)
                add_arch("sparc64", res)
            elif archdir == "sh":
                add_arch("sh64", res)
            else:
                # For most architectures, ARCH = SRCARCH
                add_arch(archdir, res)

    # Don't want subsequent 'make *config' commands in tests to see this
    del os.environ["ARCH"]
    del os.environ["SRCARCH"]

    return res

def test_all_no(conf):
    """Test if our allnoconfig implementation generates the same .config as 'make allnoconfig', for all architectures"""

    while True:
        done = True

        for sym in conf:
            # Choices take care of themselves for allnoconf, so we only need to
            # worry about non-choice symbols
            if not sym.is_choice_item():
                lower_bound = sym.get_lower_bound()

                # If we can assign a lower value to the symbol (where "n", "m" and
                # "y" are ordered from lowest to highest), then do so.
                # lower_bound() returns None for symbols whose values cannot
                # (currently) be changed, as well as for non-bool, non-tristate
                # symbols.
                if lower_bound is not None and \
                   kconfiglib.tri_less(lower_bound, sym.calc_value()):

                    sym.set_value(lower_bound)

                    # We just changed the value of some symbol. As this may effect
                    # other symbols, we need to keep looping.
                    done = False

        if done:
            break

    conf.write_config("._config")

    shell("make allnoconfig")

def test_all_yes(conf):
    """Test if our allyesconfig implementation generates the same .config as 'make allyesconfig', for all architectures"""

    # Get a list of all symbols that are not choice items
    non_choice_syms = [sym for sym in conf.get_symbols() if
                       not sym.is_choice_item()]

    while True:
        done = True

        # Handle symbols outside of choices

        for sym in non_choice_syms:
            upper_bound = sym.get_upper_bound()

            # See corresponding comment for allnoconf implementation
            if upper_bound is not None and \
               kconfiglib.tri_less(sym.calc_value(), upper_bound):
                sym.set_value(upper_bound)
                done = False

        # Handle symbols within choices

        for choice in conf.get_choices():

            # Handle choices whose visibility allow them to be in "y" mode

            if choice.get_visibility() == "y":
                selection = choice.get_selection_from_defaults()
                if selection is not None and \
                   selection is not choice.get_user_selection():
                    selection.set_value("y")
                    done = False

            # Handle choices whose visibility only allow them to be in "m" mode

            elif choice.get_visibility() == "m":
                for sym in choice.get_items():
                    if sym.calc_value() != "m" and \
                       sym.get_upper_bound() != "n":
                        sym.set_value("m")
                        done = False


        if done:
            break

    conf.write_config("._config")

    shell("make allyesconfig")

def test_call_all(conf):
    """Call all public methods on all symbols, menus, choices and comments (nearly all public methods: some are hard to test like this, but are exercised by other tests) for all architectures to make sure we never crash or hang"""
    print "  For {0}...".format(conf.get_arch())

    conf.get_arch()
    conf.get_defconfig_filename()
    conf.get_top_level_items()
    conf.eval("y && ARCH")

    # Syntax error
    caught_exception = False
    try:
        conf.eval("y && && y")
    except kconfiglib.Kconfig_Syntax_Error:
        caught_exception = True

    if not caught_exception:
        print "Fail: no exception generated for expression with syntax error"
        fail()

    conf.get_config_header()
    conf.get_base_dir()
    conf.reset()
    conf.get_symbols(False)
    conf.get_mainmenu_text()

    for s in conf.get_symbols():
        s.reset()
        s.calc_value()
        s.calc_default_value()
        s.get_user_value()
        s.get_name()
        s.get_upper_bound()
        s.get_lower_bound()
        s.get_assignable_values()
        s.get_type()
        s.get_visibility()
        s.get_prompt()
        s.get_parent()
        s.get_sibling_symbols()
        s.get_sibling_items()
        s.get_referenced_symbols()
        s.get_referenced_symbols(True)
        s.get_selected_symbols()
        s.get_help()
        s.get_config()
        s.get_def_locations()
        s.get_ref_locations()
        s.is_modifiable()
        s.is_defined()
        s.is_special()
        s.is_from_environment()
        s.has_ranges()
        s.is_choice_item()
        s.is_choice_selection()
        s.__str__()

    for c in conf.get_choices():
        if c.get_name() is not None:
            print "LOOOOOOOOL", c.get_name()
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
        c.get_prompt()
        c.calc_mode()
        c.is_optional()
        c.__str__()

    for m in conf.get_menus():
        m.get_items()
        m.get_symbols(False)
        m.get_symbols(True)
        m.get_depends_on_visibility()
        m.get_visible_if_visibility()
        m.get_title()
        m.get_visibility()
        m.get_parent()
        m.get_referenced_symbols()
        m.get_referenced_symbols(True)
        m.get_location()
        m.__str__()

    for c in conf.get_comments():
        c.get_text()
        c.get_visibility()
        c.get_parent()
        c.get_referenced_symbols()
        c.get_referenced_symbols(True)
        c.get_location()
        c.__str__()

def test_config_absent(conf):
    """Test if kconfiglib generates the same configuration as 'conf' without a .config, for each architecture"""
    conf.write_config("._config")

    shell("make alldefconfig")

def test_defconfig(conf):
    """Test if kconfiglib generates the same .config as conf for each architecture/defconfig pair (this takes two hours on a Core i7@2.67 GHz system)"""
    # Collect defconfigs of the current ARCH. 

    global nconfigs

    defconfigs = []

    arch_dir = os.path.join("arch", os.environ["SRCARCH"])

    # Some arches have a "defconfig" in their
    # arch directory.
    defconfig = os.path.join(arch_dir, "defconfig")
    if os.path.exists(defconfig):
        defconfigs.append([defconfig, "defconfig"])

    defconfigs_dir = os.path.join(arch_dir, "configs")
    if os.path.isdir(defconfigs_dir):
        for root,dirs,files in os.walk(defconfigs_dir):
            for c in files:
                defconfig = os.path.join(root, c)
                makedefconfig = os.path.join(os.path.relpath(root, defconfigs_dir), c)

                if not c.endswith("_defconfig"):
                    print "Fail: unexpected defconfig filename (should be end with \"_defconfig\"): " + defconfig	
                    fail()

                defconfigs.append([defconfig, makedefconfig])

    # Test architecture for each defconfig

    for defconfig,makedefconfig in defconfigs:
        rm_configs()

        nconfigs += 1

        conf.load_config(defconfig)
        conf.write_config("._config")

        # make defconfig or make xxx_defconfig
        shell("make " + makedefconfig)

        sys.stdout.write("  {0:<14}with {1:<60} ".format(conf.get_arch(), defconfig))

        if equal_confs():
            print "OK"
        else:
            print "FAIL"
            fail()

#
# Helper functions
#

def shell(cmd):
    subprocess.Popen(cmd,
                     shell = True,
                     stdout = subprocess.PIPE,
                     stderr = subprocess.PIPE).wait()

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

def fail():
    global _all_ok
    _all_ok = False

def all_ok():
    return _all_ok

if __name__ == "__main__":
    run_tests()
