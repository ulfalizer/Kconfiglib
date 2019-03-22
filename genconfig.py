#!/usr/bin/env python

# Copyright (c) 2018-2019, Ulf Magnusson
# SPDX-License-Identifier: ISC

"""
Generates a header file with #defines from the configuration, matching the
format of include/generated/autoconf.h in the Linux kernel.

Optionally creates/updates a directory structure with one file per symbol that
can be used to implement incremental builds. See the docstring for
Kconfig.sync_deps() in kconfiglib.py.

By default, the configuration is generated from '.config'. A different
configuration file can be passed in the KCONFIG_CONFIG environment variable.
"""
import argparse

import kconfiglib


DEFAULT_HEADER_PATH = "config.h"
DEFAULT_SYNC_DEPS_PATH = "deps/"


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=__doc__)

    parser.add_argument(
        "--header-path",
        metavar="HEADER_FILE",
        default=DEFAULT_HEADER_PATH,
        help="Path for the generated header file (default: {})"
             .format(DEFAULT_HEADER_PATH))

    parser.add_argument(
        "--sync-deps",
        dest="sync_deps_path",
        metavar="OUTPUT_DIR",
        nargs="?",
        const=DEFAULT_SYNC_DEPS_PATH,
        help="Enable generation of build dependency information for "
             "incremental builds, optionally specifying the output path "
             "(default: {})".format(DEFAULT_SYNC_DEPS_PATH))

    parser.add_argument(
        "--config-out",
        dest="config_path",
        metavar="CONFIG_FILE",
        help="Write the configuration to the specified filename. "
             "This is useful if you include .config files in Makefiles, as "
             "the generated configuration file will be a full .config file "
             "even if .config is outdated. The generated configuration "
             "matches what olddefconfig would produce. If you use "
             "--sync-deps, you can include deps/auto.conf instead. "
             "--config-out is meant for cases where incremental build "
             "information isn't needed.")

    parser.add_argument(
        "kconfig_filename",
        metavar="KCONFIG_FILENAME",
        nargs="?",
        default="Kconfig",
        help="Top-level Kconfig file (default: Kconfig)")

    args = parser.parse_args()


    kconf = kconfiglib.Kconfig(args.kconfig_filename)
    kconf.load_config(verbose=False)

    kconf.write_autoconf(args.header_path)

    if args.sync_deps_path is not None:
        kconf.sync_deps(args.sync_deps_path)

    if args.config_path is not None:
        kconf.write_config(args.config_path, save_old=False)


if __name__ == "__main__":
    main()
