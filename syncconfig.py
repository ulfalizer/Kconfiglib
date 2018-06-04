#!/usr/bin/env python

# This script can be used to implement incremental builds, where changing a
# symbol will recompile just the source files that reference it.
#
# See the docstring for the Kconfig.sync_deps() function for more usage
# information.
#
# Usage:
#
#   (Automatically) run the following command before each build:
#
#     $ syncconfig [<top Kconfig file>] <symbol file directory, passed to sync_deps()>
#
#   This will indirectly catch any (relevant) changes to Kconfig files and
#   environment variables as well, so it's redundant to have separate
#   dependencies for those (except as a slight optimization).

import sys

import kconfiglib

def main():
    if not 2 <= len(sys.argv) <= 3:
        sys.exit("usage: {} [Kconfig] <Symbol directory>".format(sys.argv[0]))

    if len(sys.argv) == 2:
        kconfig_filename = "Kconfig"
        sym_dir = sys.argv[1]
    else:
        kconfig_filename = sys.argv[1]
        sym_dir = sys.argv[2]

    kconfiglib.Kconfig(kconfig_filename).sync_deps(sym_dir)

if __name__ == "__main__":
    main()
