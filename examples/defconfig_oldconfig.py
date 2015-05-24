# Produces exactly the same output as the following script:
#
# make defconfig
# echo CONFIG_ETHERNET=n >> .config
# make oldconfig
# echo CONFIG_ETHERNET=y >> .config
# yes n | make oldconfig
#
# This came up in https://github.com/ulfalizer/Kconfiglib/issues/15.

import kconfiglib
import sys

conf = kconfiglib.Config(sys.argv[1])

# Mirrors defconfig
conf.load_config("arch/x86/configs/x86_64_defconfig")
conf.write_config(".config")

# Mirrors the first oldconfig
conf.load_config(".config")
conf["ETHERNET"].set_user_value('n')
conf.write_config(".config")

# Mirrors the second oldconfig
conf.load_config(".config")
conf["ETHERNET"].set_user_value('y')
for s in conf:
    if s.get_user_value() is None and 'n' in s.get_assignable_values():
        s.set_user_value('n')

# Write the final configuration
conf.write_config(".config")
