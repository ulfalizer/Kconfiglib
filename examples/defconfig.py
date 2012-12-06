# Works like entering "make menuconfig" and immediately saving and exiting

import kconfiglib
import os
import sys

conf = kconfiglib.Config(sys.argv[1])

if os.path.exists(".config"):
    conf.load_config(".config")
else:
    defconfig = conf.get_defconfig_filename()
    if defconfig is not None:
        print "Using " + defconfig
        conf.load_config(defconfig)

conf.write_config(".config")
