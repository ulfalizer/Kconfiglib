# Works like entering "make menuconfig" and immediately saving and exiting
#
# Usage:
#
#   $ make [ARCH=<arch>] scriptconfig SCRIPT=Kconfiglib/examples/allyesconfig.py

import kconfiglib
import os
import sys

kconf = kconfiglib.Kconfig(sys.argv[1])

if os.path.exists(".config"):
    print("using existing .config")
    kconf.load_config(".config")
else:
    if kconf.defconfig_filename is not None:
        print("using " + kconf.defconfig_filename)
        kconf.load_config(kconf.defconfig_filename)

kconf.write_config(".config")
print("configuration written to .config")
