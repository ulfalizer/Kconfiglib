# Works like entering "make menuconfig" and immediately saving and exiting
#
# Usage:
#
#   $ make [ARCH=<arch>] scriptconfig SCRIPT=Kconfiglib/examples/allyesconfig.py

import kconfiglib
import os
import sys

conf = kconfiglib.Config(sys.argv[1])

if os.path.exists(".config"):
    print("using existing .config")
    conf.load_config(".config")
else:
    if conf.defconfig_filename is not None:
        print("using " + conf.defconfig_filename)
        conf.load_config(conf.defconfig_filename)

conf.write_config(".config")
print("configuration written to .config")
