# Produces exactly the same output as the following script:
#
# make defconfig
# echo CONFIG_ETHERNET=n >> .config
# make oldconfig
# echo CONFIG_ETHERNET=y >> .config
# yes n | make oldconfig
#
# This came up in https://github.com/ulfalizer/Kconfiglib/issues/15.
#
# Usage:
#
#   $ make [ARCH=<arch>] scriptconfig SCRIPT=Kconfiglib/examples/defconfig_oldconfig.py

import kconfiglib
import sys

conf = kconfiglib.Kconfig(sys.argv[1])

# Mirrors defconfig
conf.load_config("arch/x86/configs/x86_64_defconfig")
conf.write_config(".config")

# Mirrors the first oldconfig
conf.load_config(".config")
conf.syms["ETHERNET"].set_value(0)
conf.write_config(".config")

# Mirrors the second oldconfig
conf.load_config(".config")
conf.syms["ETHERNET"].set_value(2)
for s in conf:
    if s.user_value is None and 0 in s.assignable:
        s.set_value(0)

# Write the final configuration
conf.write_config(".config")
