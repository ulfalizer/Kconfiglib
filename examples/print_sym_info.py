# Loads a Kconfig and a .config and prints information about a symbol.

import kconfiglib
import sys

# Create a Config object representing a Kconfig configuration. (Any number of
# these can be created -- the library has no global state.)
conf = kconfiglib.Config(sys.argv[1])

# Load values from a .config file. 'srctree' is an environment variable set by
# the Linux makefiles to the top-level directory of the kernel tree. It needs
# to be used here for the script to work with alternative build directories
# (specified e.g. with O=).
conf.load_config("$srctree/arch/x86/configs/i386_defconfig")

# Print some information about a symbol. (The Config class implements
# __getitem__() to provide a handy syntax for getting symbols.)
print conf["SERIAL_UARTLITE_CONSOLE"]
