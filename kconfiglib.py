# This is Kconfiglib, a Python library for scripting, debugging, and extracting
# information from Kconfig-based configuration systems. To view the
# documentation, run
#
#  $ pydoc kconfiglib
#
# or, if you prefer HTML,
#
#  $ pydoc -w kconfiglib
#
# The examples/ subdirectory contains examples, to be run with e.g.
#
#  $ make scriptconfig SCRIPT=Kconfiglib/examples/print_tree.py
#
# Look in testsuite.py for the test suite.

"""
Kconfiglib is a Python library for scripting and extracting information from
Kconfig-based configuration systems. Features include the following:

 - Symbol values and properties can be looked up and values assigned
   programmatically.
 - .config files can be read and written.
 - Expressions can be evaluated in the context of a Kconfig configuration.
 - Relations between symbols can be quickly determined, such as finding all
   symbols that reference a particular symbol.
 - Highly compatible with the scripts/kconfig/*conf utilities. The test suite
   automatically compares outputs between Kconfiglib and the C implementation
   for a large number of cases.

For the Linux kernel, scripts are run using

 $ make scriptconfig [ARCH=<arch>] SCRIPT=<path to script> [SCRIPT_ARG=<arg>]

Using the 'scriptconfig' target ensures that required environment variables
(SRCARCH, ARCH, srctree, KERNELVERSION, etc.) are set up correctly.

Scripts receive the name of the Kconfig file to load in sys.argv[1]. As of
Linux 4.1.0-rc5, this is always "Kconfig" from the kernel top-level directory.
If an argument is provided with SCRIPT_ARG, it appears as sys.argv[2].

To get an interactive Python prompt with Kconfiglib preloaded and a Config
object 'c' created, run

 $ make iscriptconfig [ARCH=<arch>]

Kconfiglib supports both Python 2 and Python 3. For (i)scriptconfig, the Python
interpreter to use can be passed in PYTHONCMD, which defaults to 'python'. PyPy
works well too, and might give a nice speedup for long-running jobs.

The examples/ directory contains short example scripts, which can be run with
e.g.

 $ make scriptconfig SCRIPT=Kconfiglib/examples/print_tree.py

or

 $ make scriptconfig SCRIPT=Kconfiglib/examples/help_grep.py SCRIPT_ARG=kernel

testsuite.py contains the test suite. See the top of the script for how to run
it.

Credits: Written by Ulf "Ulfalizer" Magnusson

Send bug reports, suggestions and other feedback to ulfalizer a.t Google's
email service. Don't wrestle with internal APIs. Tell me what you need and I
might add it in a safe way as a client API instead."""

import os
import platform
import re
import sys

# File layout:
#
# Public classes
# Public functions
# Internal classes
# Internal functions
# Public global constants
# Internal global constants

# Line length: 79 columns

#
# Public classes
#

class Config(object):

    """Represents a Kconfig configuration, e.g. for i386 or ARM. This is the
    set of symbols and other items appearing in the configuration together with
    their values. Creating any number of Config objects -- including for
    different architectures -- is safe; Kconfiglib has no global state."""

    #
    # Public interface
    #

    def __init__(self, filename="Kconfig", base_dir=None, print_warnings=True,
                 print_undef_assign=False):
        """Creates a new Config object, representing a Kconfig configuration.
        Raises Kconfig_Syntax_Error on syntax errors.

        filename (default: "Kconfig"): The base Kconfig file of the
           configuration. For the Linux kernel, you'll probably want "Kconfig"
           from the top-level directory, as environment variables will make
           sure the right Kconfig is included from there
           (arch/<architecture>/Kconfig). If you are using Kconfiglib via 'make
           scriptconfig', the filename of the base base Kconfig file will be in
           sys.argv[1].

        base_dir (default: None): The base directory relative to which 'source'
           statements within Kconfig files will work. For the Linux kernel this
           should be the top-level directory of the kernel tree. $-references
           to existing environment variables will be expanded.

           If None (the default), the environment variable 'srctree' will be
           used if set, and the current directory otherwise. 'srctree' is set
           by the Linux makefiles to the top-level kernel directory. A default
           of "." would not work with an alternative build directory.

        print_warnings (default: True): Set to True if warnings related to this
           configuration should be printed to stderr. This can be changed later
           with Config.set_print_warnings(). It is provided as a constructor
           argument since warnings might be generated during parsing.

        print_undef_assign (default: False): Set to True if informational
           messages related to assignments to undefined symbols should be
           printed to stderr for this configuration. Can be changed later with
           Config.set_print_undef_assign()."""

        # The set of all symbols, indexed by name (a string)
        self._syms = {}

        # The set of all defined symbols in the configuration in the order they
        # appear in the Kconfig files. This excludes the special symbols n, m,
        # and y as well as symbols that are referenced but never defined.
        self._defined_syms = []

        # The set of all named choices (yes, choices can have names), indexed
        # by name (a string)
        self._named_choices = {}

        # Lists containing all choices, menus, and comments in the
        # configuration
        self._choices = []
        self._menus = []
        self._comments = []

        def register_special_symbol(type_, name, val):
            sym = Symbol()
            sym._is_special = True
            sym._is_defined = True
            sym._config = self
            sym._name = name
            sym._type = type_
            sym._cached_val = val
            self._syms[name] = sym
            return sym

        # The special symbols n, m and y, used as shorthand for "n", "m" and
        # "y"
        self._n = register_special_symbol(TRISTATE, "n", "n")
        self._m = register_special_symbol(TRISTATE, "m", "m")
        self._y = register_special_symbol(TRISTATE, "y", "y")
        # DEFCONFIG_LIST uses this
        register_special_symbol(STRING, "UNAME_RELEASE", platform.uname()[2])

        # The symbol with "option defconfig_list" set, containing a list of
        # default .config files
        self._defconfig_sym = None

        # See Symbol.get_(src)arch()
        self._arch = os.environ.get("ARCH")
        self._srcarch = os.environ.get("SRCARCH")

        # If you set CONFIG_ in the environment, Kconfig will prefix all
        # symbols with its value when saving the configuration, instead of
        # using the default, "CONFIG_".
        self._config_prefix = os.environ.get("CONFIG_")
        if self._config_prefix is None:
            self._config_prefix = "CONFIG_"

        # Regular expressions for parsing .config files
        self._set_re = re.compile(r"{}(\w+)=(.*)"
                                  .format(self._config_prefix))
        self._unset_re = re.compile(r"# {}(\w+) is not set"
                                    .format(self._config_prefix))

        self._kconfig_filename = filename

        # See Config.__init__(). We need this for get_defconfig_filename().
        self._srctree = os.environ.get("srctree")

        if base_dir is None:
            self._base_dir = "." if self._srctree is None else self._srctree
        else:
            self._base_dir = os.path.expandvars(base_dir)

        # The 'mainmenu' text
        self._mainmenu_text = None

        # The filename of the most recently loaded .config file
        self._config_filename = None
        # The textual header of the most recently loaded .config, uncommented
        self._config_header = None

        self._print_warnings = print_warnings
        self._print_undef_assign = print_undef_assign

        # When parsing properties, we stop on the first (non-empty)
        # non-property line. _end_line and _end_line_tokens hold that line and
        # its tokens so that we don't have to re-tokenize the line later. This
        # isn't just an optimization: We record references to symbols during
        # tokenization, so tokenizing twice would cause double registration.
        #
        # self._end_line doubles as a flag where None means we don't have a
        # cached tokenized line.
        self._end_line = None
        # self.end_line_tokens is set later during parsing

        # Parse the Kconfig files
        self._top_block = []
        self._parse_file(filename, None, None, None, self._top_block)

        # Build Symbol._dep for all symbols
        self._build_dep()

    def get_arch(self):
        """Returns the value the environment variable ARCH had at the time the
        Config instance was created, or None if ARCH was not set. For the
        kernel, this corresponds to the architecture being built for, with
        values such as "i386" or "mips"."""
        return self._arch

    def get_srcarch(self):
        """Returns the value the environment variable SRCARCH had at the time
        the Config instance was created, or None if SRCARCH was not set. For
        the kernel, this corresponds to the particular arch/ subdirectory
        containing architecture-specific code."""
        return self._srcarch

    def get_srctree(self):
        """Returns the value the environment variable 'srctree' had at the time
        the Config instance was created, or None if 'srctree' was not defined.
        This variable points to the source directory and is used when building
        in a separate directory."""
        return self._srctree

    def get_base_dir(self):
        """Returns the base directory relative to which 'source' statements
        will work, passed as an argument to Config.__init__()."""
        return self._base_dir

    def get_kconfig_filename(self):
        """Returns the name of the (base) kconfig file this configuration was
        loaded from."""
        return self._kconfig_filename

    def get_config_filename(self):
        """Returns the filename of the most recently loaded configuration file,
        or None if no configuration has been loaded."""
        return self._config_filename

    def get_config_header(self):
        """Returns the (uncommented) textual header of the .config file most
        recently loaded with load_config(). Returns None if no .config file has
        been loaded or if the most recently loaded .config file has no header.

        The header consists of all lines up to but not including the first line
        that either (1) does not begin with "#", or (2) matches
        "# CONFIG_FOO is not set"."""
        return self._config_header

    def get_mainmenu_text(self):
        """Returns the text of the 'mainmenu' statement (with $-references to
        symbols replaced by symbol values), or None if the configuration has no
        'mainmenu' statement."""
        return None if self._mainmenu_text is None else \
          self._expand_sym_refs(self._mainmenu_text)

    def get_defconfig_filename(self):
        """Returns the name of the defconfig file, which is the first existing
        file in the list given in a symbol having 'option defconfig_list' set.
        $-references to symbols will be expanded ("$FOO bar" -> "foo bar" if
        FOO has the value "foo"). Returns None in case of no defconfig file.
        Setting 'option defconfig_list' on multiple symbols ignores the symbols
        past the first one (and prints a warning).

        If the environment variable 'srctree' was set when the Config was
        created, each defconfig specified with a relative path will be
        searched for in $srcdir if it is not found at the specified path (i.e.,
        if foo/defconfig is not found, $srctree/foo/defconfig will be looked
        up).

        WARNING: A wart here is that scripts/kconfig/Makefile sometimes uses
        the --defconfig=<defconfig> option when calling the C implementation of
        e.g. 'make defconfig'. This option overrides the 'option
        defconfig_list' symbol, meaning the result from
        get_defconfig_filename() might not match what 'make defconfig' would
        use. That probably ought to be worked around somehow, so that this
        function always gives the "expected" result."""
        if self._defconfig_sym is None:
            return None
        for filename, cond_expr in self._defconfig_sym._def_exprs:
            if self._eval_expr(cond_expr) != "n":
                filename = self._expand_sym_refs(filename)
                if os.access(filename, os.R_OK):
                    return filename
                # defconfig not found. If the path is a relative path and
                # $srctree is set, we also look in $srctree.
                if not os.path.isabs(filename) and self._srctree is not None:
                    filename = os.path.join(self._srctree, filename)
                    if os.access(filename, os.R_OK):
                        return filename

        return None

    def get_symbol(self, name):
        """Returns the symbol with name 'name', or None if no such symbol
        appears in the configuration. An alternative shorthand is conf[name],
        where conf is a Config instance, though that will instead raise
        KeyError if the symbol does not exist."""
        return self._syms.get(name)

    def __getitem__(self, name):
        """Returns the symbol with name 'name'. Raises KeyError if the symbol
        does not appear in the configuration."""
        return self._syms[name]

    def get_symbols(self, all_symbols=True):
        """Returns a list of symbols from the configuration. An alternative for
        iterating over all defined symbols (in the order of definition) is

        for sym in config:
            ...

        which relies on Config implementing __iter__() and is equivalent to

        for sym in config.get_symbols(False):
            ...

        all_symbols (default: True): If True, all symbols -- including special
           and undefined symbols -- will be included in the result, in an
           undefined order. If False, only symbols actually defined and not
           merely referred to in the configuration will be included in the
           result, and will appear in the order that they are defined within
           the Kconfig configuration files."""
        return list(self._syms.values()) if all_symbols else \
               self._defined_syms

    def __iter__(self):
        """Convenience function for iterating over the set of all defined
        symbols in the configuration, used like

        for sym in conf:
            ...

        The iteration happens in the order of definition within the Kconfig
        configuration files. Symbols only referred to but not defined will not
        be included, nor will the special symbols n, m, and y. If you want to
        include such symbols as well, see config.get_symbols()."""
        return iter(self._defined_syms)

    def get_choices(self):
        """Returns a list containing all choice statements in the
        configuration, in the order they appear in the Kconfig files."""
        return self._choices

    def get_menus(self):
        """Returns a list containing all menus in the configuration, in the
        order they appear in the Kconfig files."""
        return self._menus

    def get_comments(self):
        """Returns a list containing all comments in the configuration, in the
        order they appear in the Kconfig files."""
        return self._comments

    def get_top_level_items(self):
        """Returns a list containing the items (symbols, menus, choices, and
        comments) at the top level of the configuration -- that is, all items
        that do not appear within a menu or choice. The items appear in the
        same order as within the configuration."""
        return self._top_block

    def load_config(self, filename, replace=True):
        """Loads symbol values from a file in the familiar .config format.
        Equivalent to calling Symbol.set_user_value() to set each of the
        values.

        "# CONFIG_FOO is not set" within a .config file is treated specially
        and sets the user value of FOO to 'n'. The C implementation works the
        same way.

        filename: The .config file to load. $-references to existing
          environment variables will be expanded. For scripts to work even when
          an alternative build directory is used with the Linux kernel, you
          need to refer to the top-level kernel directory with "$srctree".

        replace (default: True): True if the configuration should replace the
           old configuration; False if it should add to it."""

        # Put this first so that a missing file doesn't screw up our state
        filename = os.path.expandvars(filename)
        line_feeder = _FileFeed(filename)

        self._config_filename = filename

        #
        # Read header
        #

        if not self._is_header_line(line_feeder.peek_next()):
            self._config_header = None
        else:
            # Kinda inefficient, but this is an unlikely hotspot
            self._config_header = ""
            while self._is_header_line(line_feeder.peek_next()):
                self._config_header += line_feeder.get_next()[1:]
            # Makes c.write_config(".config", c.get_config_header()) preserve
            # the header exactly. We also handle weird cases like a .config
            # file with just "# foo" and no trailing newline in it (though we
            # would never generate that ourselves), hence the slight
            # awkwardness.
            if self._config_header.endswith("\n"):
                self._config_header = self._config_header[:-1]

        #
        # Read assignments. Hotspot for some workloads.
        #

        if replace:
            # This invalidates all symbols as a side effect
            self.unset_user_values()
        else:
            self._invalidate_all()

        # Small optimization
        set_re_match = self._set_re.match
        unset_re_match = self._unset_re.match

        while 1:
            line = line_feeder.get_next()
            if line is None:
                return

            line = line.rstrip()

            set_match = set_re_match(line)
            if set_match:
                name, val = set_match.groups()
                if name not in self._syms:
                    self._warn_undef_assign_load(
                        name, val, line_feeder.filename, line_feeder.linenr)
                    continue

                sym = self._syms[name]

                if sym._type == STRING and val.startswith('"'):
                    if len(val) < 2 or val[-1] != '"':
                        self._warn("malformed string literal",
                                   line_feeder.filename,
                                   line_feeder.linenr)
                        continue
                    # Strip quotes and remove escapings. The unescaping
                    # procedure should be safe since " can only appear as \"
                    # inside the string.
                    val = val[1:-1].replace('\\"', '"') \
                                   .replace("\\\\", "\\")

                if sym._is_choice_sym:
                    user_mode = sym._parent._user_mode
                    if user_mode is not None and user_mode != val:
                        self._warn("assignment to {} changes mode of "
                                   'containing choice from "{}" to "{}".'
                                   .format(name, val, user_mode),
                                   line_feeder.filename,
                                   line_feeder.linenr)

            else:
                unset_match = unset_re_match(line)
                if not unset_match:
                    continue

                name = unset_match.group(1)
                if name not in self._syms:
                    self._warn_undef_assign_load(
                        name, val, line_feeder.filename, line_feeder.linenr)
                    continue

                sym = self._syms[name]
                val = "n"

            # Done parsing the assignment. Set the value.

            if sym._user_val is not None:
                self._warn('{} set more than once. Old value: "{}", new '
                           'value: "{}".'
                           .format(name, sym._user_val, val),
                           line_feeder.filename, line_feeder.linenr)

            sym._set_user_value_no_invalidate(val, True)

    def write_config(self, filename, header=None):
        """Writes out symbol values in the familiar .config format.

        Kconfiglib makes sure the format matches what the C implementation
        would generate, down to whitespace. This eases testing.

        filename: The filename under which to save the configuration.

        header (default: None): A textual header that will appear at the
           beginning of the file, with each line commented out automatically.
           Does not need to include a trailing newline. None means no
           header."""

        # Symbol._already_written is set to True when _add_config_strings() is
        # called on a symbol, so that symbols defined in multiple locations
        # only get one .config entry. We reset it prior to writing out a new
        # .config. It only needs to be reset for defined symbols, because
        # undefined symbols will never have _add_config_strings() called on
        # them (because they do not appear in the block structure rooted at
        # _top_block).
        #
        # The C implementation reuses _write_to_conf for this, but we cache
        # _write_to_conf together with the value and don't invalidate cached
        # values when writing .config files, so that won't work.
        for sym in self._defined_syms:
            sym._already_written = False

        # Build configuration. Avoiding string concatenation is worthwhile at
        # least for PyPy.
        config_strings = []
        add_fn = config_strings.append
        for item in self._top_block:
            item._add_config_strings(add_fn)

        with open(filename, "w") as f:
            # Write header
            if header is not None:
                f.writelines(["#" + line
                              for line in (header + "\n").splitlines(True)])
            # Write configuration
            f.writelines(config_strings)

    def eval(self, s):
        """Returns the value of the expression 's' -- where 's' is represented
        as a string -- in the context of the configuration. Raises
        Kconfig_Syntax_Error if syntax errors are detected in 's'.

        For example, if FOO and BAR are tristate symbols at least one of which
        has the value "y", then config.eval("y && (FOO || BAR)") => "y"

        This function always yields a tristate value. To get the value of
        non-bool, non-tristate symbols, use Symbol.get_value().

        The result of this function is consistent with how evaluation works for
        conditional expressions in the configuration as well as in the C
        implementation. "m" and m are rewritten as '"m" && MODULES' and 'm &&
        MODULES', respectively, and a result of "m" will get promoted to "y" if
        we're running without modules.

        Syntax checking is somewhat lax, partly to be compatible with lax
        parsing in the C implementation."""
        return self._eval_expr(self._parse_expr(self._tokenize(s, True),
                                                None,  # Current symbol/choice
                                                s,
                                                None,  # filename
                                                None,  # linenr
                                                True)) # transform_m

    def unset_user_values(self):
        """Resets the values of all symbols, as if Config.load_config() or
        Symbol.set_user_value() had never been called."""

        # set_user_value() already rejects undefined symbols, and they don't
        # need to be invalidated (because their value never changes), so we can
        # just iterate over defined symbols.

        for sym in self._defined_syms:
            # We're iterating over all symbols already, so no need for symbols
            # to invalidate their dependent symbols
            sym._unset_user_value_no_recursive_invalidate()

    def set_print_warnings(self, print_warnings):
        """Determines whether warnings related to this configuration (for
        things like attempting to assign illegal values to symbols with
        Symbol.set_user_value()) should be printed to stderr.

        print_warnings: True if warnings should be printed."""
        self._print_warnings = print_warnings

    def set_print_undef_assign(self, print_undef_assign):
        """Determines whether informational messages related to assignments to
        undefined symbols should be printed to stderr for this configuration.

        print_undef_assign: If True, such messages will be printed."""
        self._print_undef_assign = print_undef_assign

    def __str__(self):
        """Returns a string containing various information about the Config."""
        return _lines("Configuration",
                      "File                                   : " +
                      self._kconfig_filename,
                      "Base directory                         : " +
                      self._base_dir,
                      "Value of $ARCH at creation time        : " +
                      ("(not set)"
                       if self._arch is None
                       else self._arch),
                      "Value of $SRCARCH at creation time     : " +
                      ("(not set)"
                       if self._srcarch is None
                       else self._srcarch),
                      "Value of $srctree at creation time     : " +
                      ("(not set)"
                       if self._srctree is None
                       else self._srctree),
                      "Most recently loaded .config           : " +
                      ("(no .config loaded)"
                       if self._config_filename is None
                       else self._config_filename),
                      "Print warnings                         : " +
                      str(self._print_warnings),
                      "Print assignments to undefined symbols : " +
                      str(self._print_undef_assign))

    #
    # Private methods
    #

    #
    # Kconfig parsing
    #

    def _parse_file(self, filename, parent, deps, visible_if_deps, block):
        """Parses the Kconfig file 'filename'. Appends the Items in the file
        (and any file it sources) to the list passed in the 'block' parameter.
        See _parse_block() for the meaning of the parameters."""
        self._parse_block(_FileFeed(filename), None, parent, deps,
                          visible_if_deps, block)

    def _parse_block(self, line_feeder, end_marker, parent, deps,
                     visible_if_deps, block):
        """Parses a block, which is the contents of either a file or an if,
        menu, or choice statement. Appends the Items to the list passed in the
        'block' parameter.

        line_feeder: A _FileFeed instance feeding lines from a file. The
          Kconfig language is line-based in practice.

        end_marker: The token that ends the block, e.g. _T_ENDIF ("endif") for
           ifs. None for files.

        parent: The enclosing menu or choice, or None if we're at the top
           level.

        deps: Dependencies from enclosing menus, choices and ifs.

        visible_if_deps (default: None): 'visible if' dependencies from
           enclosing menus.

        block: The list to add items to."""

        while 1:
            # See the _end_line description in Config.__init__()
            if self._end_line is not None:
                line = self._end_line
                tokens = self._end_line_tokens
                self._end_line = None
            else:
                line = line_feeder.get_next()
                if line is None:
                    if end_marker is not None:
                        raise Kconfig_Syntax_Error("Unexpected end of file " +
                                                   line_feeder.filename)
                    return

                tokens = self._tokenize(line, False, line_feeder.filename,
                                        line_feeder.linenr)

            t0 = tokens.get_next()
            if t0 is None:
                continue

            # Cases are ordered roughly by frequency, which speeds things up a
            # bit

            # This also handles 'menuconfig'. See the comment in the token
            # definitions.
            if t0 == _T_CONFIG:
                # The tokenizer will automatically allocate a new Symbol object
                # for any new names it encounters, so we don't need to worry
                # about that here.
                sym = tokens.get_next()

                # Symbols defined in multiple places get the parent of their
                # first definition. However, for symbols whose parents are
                # choice statements, the choice statement takes precedence.
                if not sym._is_defined or isinstance(parent, Choice):
                    sym._parent = parent
                sym._is_defined = True

                self._parse_properties(line_feeder, sym, deps, visible_if_deps)

                self._defined_syms.append(sym)
                block.append(sym)

            elif t0 == _T_SOURCE:
                kconfig_file = tokens.get_next()
                exp_kconfig_file = self._expand_sym_refs(kconfig_file)

                # Hack: Avoid passing on a "./" prefix in the common case of
                # 'base_dir' defaulting to ".", just to give less awkward
                # results from e.g. get_def/ref_locations(). Maybe this could
                # be handled in a nicer way.
                if self._base_dir == ".":
                    filename = exp_kconfig_file
                else:
                    filename = os.path.join(self._base_dir, exp_kconfig_file)

                if not os.path.exists(filename):
                    raise IOError('{}:{}: sourced file "{}" (expands to "{}") '
                                  "not found. Perhaps base_dir (argument to "
                                  'Config.__init__(), currently "{}") is set '
                                  'to the wrong value.'
                                  .format(line_feeder.filename,
                                          line_feeder.linenr,
                                          kconfig_file, exp_kconfig_file,
                                          self._base_dir))

                # Add items to the same block
                self._parse_file(filename, parent, deps, visible_if_deps,
                                 block)

            elif t0 == end_marker:
                # We have reached the end of the block
                return

            elif t0 == _T_IF:
                # If statements are treated as syntactic sugar for adding
                # dependencies to enclosed items and do not have an explicit
                # object representation.

                dep_expr = self._parse_expr(tokens, None, line,
                                            line_feeder.filename,
                                            line_feeder.linenr, True)
                # Add items to the same block
                self._parse_block(line_feeder, _T_ENDIF, parent,
                                  _make_and(dep_expr, deps),
                                  visible_if_deps, block)

            elif t0 == _T_COMMENT:
                comment = Comment()
                comment._config = self
                comment._parent = parent
                comment._filename = line_feeder.filename
                comment._linenr = line_feeder.linenr
                comment._text = tokens.get_next()

                self._parse_properties(line_feeder, comment, deps,
                                       visible_if_deps)

                self._comments.append(comment)
                block.append(comment)

            elif t0 == _T_MENU:
                menu = Menu()
                menu._config = self
                menu._parent = parent
                menu._filename = line_feeder.filename
                menu._linenr = line_feeder.linenr
                menu._title = tokens.get_next()

                self._parse_properties(line_feeder, menu, deps,
                                       visible_if_deps)

                # This needs to go before _parse_block() so that we get the
                # proper menu ordering in the case of nested menus
                self._menus.append(menu)
                # Parse contents and put Items in menu._block
                self._parse_block(line_feeder, _T_ENDMENU, menu,
                                  menu._menu_dep,
                                  _make_and(visible_if_deps,
                                            menu._visible_if_expr),
                                  menu._block)

                block.append(menu)

            elif t0 == _T_CHOICE:
                name = tokens.get_next()
                if name is None:
                    choice = Choice()
                    self._choices.append(choice)
                else:
                    # Named choice
                    choice = self._named_choices.get(name)
                    if choice is None:
                        choice = Choice()
                        choice._name = name
                        self._named_choices[name] = choice
                        self._choices.append(choice)

                choice._config = self
                choice._parent = parent

                choice._def_locations.append((line_feeder.filename,
                                              line_feeder.linenr))

                self._parse_properties(line_feeder, choice, deps,
                                       visible_if_deps)

                # Parse contents and put Items in choice._block
                self._parse_block(line_feeder, _T_ENDCHOICE, choice, deps,
                                  visible_if_deps, choice._block)

                choice._determine_actual_symbols()

                # If no type is specified for the choice, its type is that of
                # the first choice item with a specified type
                if choice._type == UNKNOWN:
                    for item in choice._actual_symbols:
                        if item._type != UNKNOWN:
                            choice._type = item._type
                            break

                # Each choice item of UNKNOWN type gets the type of the choice
                for item in choice._actual_symbols:
                    if item._type == UNKNOWN:
                        item._type = choice._type

                block.append(choice)

            elif t0 == _T_MAINMENU:
                text = tokens.get_next()
                if self._mainmenu_text is not None:
                    self._warn("overriding 'mainmenu' text. "
                               'Old value: "{}", new value: "{}".'
                               .format(self._mainmenu_text, text),
                               line_feeder.filename, line_feeder.linenr)
                self._mainmenu_text = text

            else:
                _parse_error(line, "unrecognized construct",
                             line_feeder.filename, line_feeder.linenr)

    def _parse_cond(self, tokens, stmt, line, filename, linenr):
        """Parses an optional 'if <expr>' construct and returns the parsed
        <expr>, or None if the next token is not _T_IF."""
        return self._parse_expr(tokens, stmt, line, filename, linenr, True) \
               if tokens.check(_T_IF) else None

    def _parse_val_and_cond(self, tokens, stmt, line, filename, linenr):
        """Parses '<expr1> if <expr2>' constructs, where the 'if' part is
        optional. Returns a tuple containing the parsed expressions, with
        None as the second element if the 'if' part is missing."""
        return (self._parse_expr(tokens, stmt, line, filename, linenr, False),
                self._parse_cond(tokens, stmt, line, filename, linenr))

    def _parse_properties(self, line_feeder, stmt, deps, visible_if_deps):
        """Parsing of properties for symbols, menus, choices, and comments.
        Takes care of propagating dependencies from enclosing menus and ifs."""

        # In case the symbol is defined in multiple locations, we need to
        # remember what prompts, defaults, selects, implies, and ranges are new
        # for this definition, as "depends on" should only apply to the local
        # definition.
        new_prompt = None
        new_def_exprs = []
        new_selects = []
        new_implies = []
        new_ranges = []

        # Dependencies from 'depends on' statements
        depends_on_expr = None

        while 1:
            line = line_feeder.get_next()
            if line is None:
                break

            filename = line_feeder.filename
            linenr = line_feeder.linenr

            tokens = self._tokenize(line, False, filename, linenr)

            t0 = tokens.get_next()
            if t0 is None:
                continue

            # Cases are ordered roughly by frequency, which speeds things up a
            # bit

            if t0 == _T_DEPENDS:
                if not tokens.check(_T_ON):
                    _parse_error(line, 'expected "on" after "depends"',
                                 filename, linenr)

                depends_on_expr = \
                    _make_and(depends_on_expr,
                              self._parse_expr(tokens, stmt, line, filename,
                                               linenr, True))

            elif t0 == _T_HELP:
                # Find first non-blank (not all-space) line and get its
                # indentation
                line = line_feeder.next_nonblank()
                if line is None:
                    stmt._help = ""
                    break
                indent = _indentation(line)
                if indent == 0:
                    # If the first non-empty lines has zero indent, there is no
                    # help text
                    stmt._help = ""
                    line_feeder.unget()
                    break

                # The help text goes on till the first non-empty line with less
                # indent
                help_lines = [_deindent(line, indent)]
                while 1:
                    line = line_feeder.get_next()
                    if line is None or \
                       (not line.isspace() and _indentation(line) < indent):
                        stmt._help = "".join(help_lines)
                        break
                    help_lines.append(_deindent(line, indent))

                if line is None:
                    break

                line_feeder.unget()

            elif t0 == _T_SELECT:
                if not isinstance(stmt, Symbol):
                    _parse_error(line, "only symbols can select", filename,
                                 linenr)

                new_selects.append(
                    (tokens.get_next(),
                     self._parse_cond(tokens, stmt, line, filename, linenr)))

            elif t0 == _T_IMPLY:
                if not isinstance(stmt, Symbol):
                    _parse_error(line, "only symbols can imply", filename,
                                 linenr)

                new_implies.append(
                    (tokens.get_next(),
                     self._parse_cond(tokens, stmt, line, filename, linenr)))

            elif t0 in (_T_BOOL, _T_TRISTATE, _T_INT, _T_HEX, _T_STRING):
                stmt._type = _TOKEN_TO_TYPE[t0]
                if tokens.peek_next() is not None:
                    new_prompt = self._parse_val_and_cond(tokens, stmt, line,
                                                          filename, linenr)

            elif t0 == _T_DEFAULT:
                new_def_exprs.append(
                    self._parse_val_and_cond(
                        tokens, stmt, line, filename, linenr))

            elif t0 in (_T_DEF_BOOL, _T_DEF_TRISTATE):
                stmt._type = _TOKEN_TO_TYPE[t0]
                if tokens.peek_next() is not None:
                    new_def_exprs.append(
                        self._parse_val_and_cond(tokens, stmt, line, filename,
                                                 linenr))

            elif t0 == _T_PROMPT:
                # 'prompt' properties override each other within a single
                # definition of a symbol, but additional prompts can be added
                # by defining the symbol multiple times; hence 'new_prompt'
                # instead of 'prompt'.
                new_prompt = self._parse_val_and_cond(tokens, stmt, line,
                                                      filename, linenr)

            elif t0 == _T_RANGE:
                new_ranges.append(
                    (tokens.get_next(),
                     tokens.get_next(),
                     self._parse_cond(tokens, stmt, line, filename, linenr)))

            elif t0 == _T_OPTION:
                if tokens.check(_T_ENV) and tokens.check(_T_EQUAL):
                    env_var = tokens.get_next()

                    stmt._is_special = True
                    stmt._is_from_env = True

                    if env_var not in os.environ:
                        self._warn("the symbol {} references the non-existent "
                                   "environment variable {} and will get the "
                                   "empty string as its value. If you're "
                                   "using Kconfiglib via "
                                   "'make (i)scriptconfig', it should have "
                                   "set up the environment correctly for you. "
                                   "If you still got this message, that "
                                   "might be an error, and you should email "
                                   "ulfalizer a.t Google's email service."""
                                   .format(stmt._name, env_var),
                                   filename, linenr)

                        stmt._cached_val = ""
                    else:
                        stmt._cached_val = os.environ[env_var]

                elif tokens.check(_T_DEFCONFIG_LIST):
                    if self._defconfig_sym is None:
                        self._defconfig_sym = stmt
                    else:
                        self._warn("'option defconfig_list' set on multiple "
                                   "symbols ({0} and {1}). Only {0} will be "
                                   "used."
                                   .format(self._defconfig_sym._name,
                                           stmt._name))

                elif tokens.check(_T_MODULES):
                    # To reduce warning spam, only warn if 'option modules' is
                    # set on some symbol that isn't MODULES, which should be
                    # safe. I haven't run into any projects that make use
                    # modules besides the kernel yet, and there it's likely to
                    # keep being called "MODULES".
                    if stmt._name != "MODULES":
                        self._warn("the 'modules' option is not supported. "
                                   "Let me know if this is a problem for you; "
                                   "it shouldn't be that hard to implement. "
                                   "(Note that modules are still supported -- "
                                   "Kconfiglib just assumes the symbol name "
                                   "MODULES, like older versions of the C "
                                   "implementation did when 'option modules' "
                                   "wasn't used.)",
                                   filename, linenr)

                elif tokens.check(_T_ALLNOCONFIG_Y):
                    if not isinstance(stmt, Symbol):
                        _parse_error(line,
                                     "the 'allnoconfig_y' option is only "
                                     "valid for symbols",
                                     filename, linenr)
                    stmt._allnoconfig_y = True

                else:
                    _parse_error(line, "unrecognized option", filename, linenr)

            elif t0 == _T_VISIBLE:
                if not tokens.check(_T_IF):
                    _parse_error(line, 'expected "if" after "visible"',
                                 filename, linenr)
                if not isinstance(stmt, Menu):
                    _parse_error(line,
                                 "'visible if' is only valid for menus",
                                 filename, linenr)

                stmt._visible_if_expr = \
                    _make_and(stmt._visible_if_expr,
                              self._parse_expr(tokens, stmt, line, filename,
                                               linenr, True))

            elif t0 == _T_OPTIONAL:
                if not isinstance(stmt, Choice):
                    _parse_error(line,
                                 '"optional" is only valid for choices',
                                 filename,
                                 linenr)
                stmt._optional = True

            else:
                # See the _end_line description in Config.__init__()
                self._end_line = line
                tokens.unget_all()
                self._end_line_tokens = tokens
                break

        # Done parsing properties. Now add the new
        # prompts/defaults/selects/implies, with dependencies propagated.

        # Save original dependencies from enclosing menus and ifs
        stmt._deps_from_containing = deps

        # The parent deps + the 'depends on' deps. This is also used to
        # implicitly create menus when a symbol depends on the previous symbol,
        # hence the name. In the C implementation, it's the dependency of a
        # menu "node".
        stmt._menu_dep = _make_and(deps, depends_on_expr)

        if isinstance(stmt, (Menu, Comment)):
            # For display purposes
            stmt._orig_deps = depends_on_expr
        else:
            # Symbol or Choice

            # Propagate dependencies to prompts
            if new_prompt is not None:
                prompt, cond_expr = new_prompt

                # Propagate 'visible if' and 'depends on'
                cond_expr = _make_and(_make_and(cond_expr, visible_if_deps),
                                      depends_on_expr)

                # Version without parent dependencies, for display
                stmt._orig_prompts.append((prompt, cond_expr))

                # This is what we actually use for evaluation
                stmt._prompts.append((prompt, _make_and(cond_expr, deps)))

            # Propagate dependencies to defaults
            for val_expr, cond_expr in new_def_exprs:
                # Version without parent dependencies, for display
                stmt._orig_def_exprs.append(
                    (val_expr, _make_and(cond_expr, depends_on_expr)))

                # This is what we actually use for evaluation
                stmt._def_exprs.append(
                    (val_expr, _make_and(cond_expr, stmt._menu_dep)))

            # Propagate dependencies to ranges
            for low, high, cond_expr in new_ranges:
                # Version without parent dependencies, for display
                stmt._orig_ranges.append(
                    (low, high, _make_and(cond_expr, depends_on_expr)))

                # This is what we actually use for evaluation
                stmt._ranges.append(
                    (low, high, _make_and(cond_expr, stmt._menu_dep)))

            # Handle selects
            for target, cond_expr in new_selects:
                # Used for display
                stmt._orig_selects.append(
                    (target, _make_and(cond_expr, depends_on_expr)))

                # Modify the dependencies of the selected symbol
                target._rev_dep = \
                    _make_or(target._rev_dep,
                             _make_and(stmt, _make_and(cond_expr,
                                                       stmt._menu_dep)))

            # Handle implies
            for target, cond_expr in new_implies:
                # Used for display
                stmt._orig_implies.append(
                    (target, _make_and(cond_expr, depends_on_expr)))

                # Modify the dependencies of the implied symbol
                target._weak_rev_dep = \
                    _make_or(target._weak_rev_dep,
                             _make_and(stmt, _make_and(cond_expr,
                                                       stmt._menu_dep)))

    def _parse_expr(self, feed, cur_item, line, filename, linenr, transform_m):
        """Parses an expression from the tokens in 'feed' using a simple
        top-down approach. The result has the form
        '(<operator> <operand 1> <operand 2>)' where <operator> is e.g.
        kconfiglib._AND. If there is only one operand (i.e., no && or ||), then
        the operand is returned directly. This also goes for subexpressions.

        As an example, A && B && (!C || D == 3) is represented as the tuple
        structure (_AND, A, (_AND, B, (_OR, (_NOT, C), (_EQUAL, D, 3)))), with
        the Symbol objects stored directly in the expression.

        feed: _Feed instance containing the tokens for the expression.

        cur_item: The item (Symbol, Choice, Menu, or Comment) currently being
           parsed, or None if we're not parsing an item. Used for recording
           references to symbols.

        line: The line containing the expression being parsed.

        filename: The file containing the expression. None when using
            Config.eval().

        linenr: The line number containing the expression. None when using
            Config.eval().

        transform_m (default: False): Determines if 'm' should be rewritten to
            'm && MODULES'. See the Config.eval() docstring."""

        # Grammar:
        #
        #   expr:     and_expr ['||' expr]
        #   and_expr: factor ['&&' and_expr]
        #   factor:   <symbol> ['='/'!='/'<'/... <symbol>]
        #             '!' factor
        #             '(' expr ')'
        #
        # It helps to think of the 'expr: and_expr' case as a single-operand OR
        # (no ||), and of the 'and_expr: factor' case as a single-operand AND
        # (no &&). Parsing code is always a bit tricky.

        # Mind dump: parse_factor() and two nested loops for OR and AND would
        # work as well. The straightforward implementation there gives a
        # (op, (op, (op, A, B), C), D) parse for A op B op C op D. Representing
        # expressions as (op, [list of operands]) instead goes nicely with that
        # version, but is wasteful for short expressions and complicates
        # expression evaluation and other code that works on expressions (more
        # complicated code likely offsets any performance gain from less
        # recursion too). If we also try to optimize the list representation by
        # merging lists when possible (e.g. when ANDing two AND expressions),
        # we end up allocating a ton of lists instead of reusing expressions,
        # which is bad.

        and_expr = self._parse_and_expr(feed, cur_item, line, filename,
                                        linenr, transform_m)

        # Return 'and_expr' directly if we have a "single-operand" OR.
        # Otherwise, parse the expression on the right and make an _OR node.
        # This turns A || B || C || D into
        # (_OR, A, (_OR, B, (_OR, C, D))).
        return and_expr \
               if not feed.check(_T_OR) else \
               (_OR, and_expr, self._parse_expr(feed, cur_item, line, filename,
                                                linenr, transform_m))

    def _parse_and_expr(self, feed, cur_item, line, filename, linenr,
                        transform_m):

        factor = self._parse_factor(feed, cur_item, line, filename, linenr,
                                    transform_m)

        # Return 'factor' directly if we have a "single-operand" AND.
        # Otherwise, parse the right operand and make an _AND node. This turns
        # A && B && C && D into (_AND, A, (_AND, B, (_AND, C, D))).
        return factor \
               if not feed.check(_T_AND) else \
               (_AND, factor, self._parse_and_expr(feed, cur_item, line,
                                                   filename, linenr,
                                                   transform_m))

    def _parse_factor(self, feed, cur_item, line, filename, linenr,
                      transform_m):
        token = feed.get_next()

        if isinstance(token, (Symbol, str)):
            # Plain symbol or relation

            next_token = feed.peek_next()
            if next_token not in _TOKEN_TO_RELATION:
                # Plain symbol

                # For conditional expressions ('depends on <expr>',
                # '... if <expr>', etc.), "m" and m are rewritten to
                # "m" && MODULES.
                if transform_m and (token is self._m or token == "m"):
                    return (_AND, "m", self._lookup_sym("MODULES"))

                return token

            # Relation
            return (_TOKEN_TO_RELATION[feed.get_next()],
                    token,
                    feed.get_next())

        if token == _T_NOT:
            return (_NOT, self._parse_factor(feed, cur_item, line, filename,
                                             linenr, transform_m))

        if token == _T_OPEN_PAREN:
            expr_parse = self._parse_expr(feed, cur_item, line, filename,
                                          linenr, transform_m)
            if not feed.check(_T_CLOSE_PAREN):
                _parse_error(line, "missing end parenthesis", filename, linenr)
            return expr_parse

        _parse_error(line, "malformed expression", filename, linenr)

    def _tokenize(self, s, for_eval, filename=None, linenr=None):
        """Returns a _Feed instance containing tokens derived from the string
        's'. Registers any new symbols encountered (via _lookup_sym()).

        Tries to be reasonably speedy by processing chunks of text via regexes
        and string operations where possible. This is a hotspot during parsing.

        for_eval: True when parsing an expression for a call to Config.eval(),
           in which case we should not treat the first token specially nor
           register new symbols."""

        # Tricky implementation detail: While parsing a token, 'token' refers
        # to the previous token. See _NOT_REF for why this is needed.

        if for_eval:
            token = None
            tokens = []

            # The current index in the string being tokenized
            i = 0

        else:
            # See comment at _initial_token_re_match definition
            initial_token_match = _initial_token_re_match(s)
            if not initial_token_match:
                return _Feed(())

            keyword = _get_keyword(initial_token_match.group(1))
            if keyword == _T_HELP:
                # Avoid junk after "help", e.g. "---", being registered as a
                # symbol
                return _Feed((_T_HELP,))
            if keyword is None:
                # We expect a keyword as the first token
                _tokenization_error(s, filename, linenr)

            token = keyword
            tokens = [keyword]
            # The current index in the string being tokenized
            i = initial_token_match.end()

        # Main tokenization loop (for tokens past the first one)
        while i < len(s):
            # Test for an identifier/keyword first. This is the most common
            # case.
            id_keyword_match = _id_keyword_re_match(s, i)
            if id_keyword_match:
                # We have an identifier or keyword

                # Jump past it
                i = id_keyword_match.end()

                # Check what it is. lookup_sym() will take care of allocating
                # new symbols for us the first time we see them. Note that
                # 'token' still refers to the previous token.

                name = id_keyword_match.group(1)
                keyword = _get_keyword(name)
                if keyword is not None:
                    # It's a keyword
                    token = keyword

                elif token not in _NOT_REF:
                    # It's a symbol reference
                    token = self._lookup_sym(name, for_eval)
                    token._ref_locations.append((filename, linenr))

                elif token == _T_CONFIG:
                    # It's a symbol definition
                    token = self._lookup_sym(name, for_eval)
                    token._def_locations.append((filename, linenr))

                else:
                    # It's a case of missing quotes. For example, the
                    # following is accepted:
                    #
                    #   menu unquoted_title
                    #
                    #   config A
                    #       tristate unquoted_prompt
                    #
                    #   endmenu
                    token = name

            else:
                # Not an identifier/keyword

                # Note: _id_keyword_match and _initial_token_match strip
                # trailing whitespace, making it safe to assume s[i] is the
                # start of a token here. We manually strip trailing whitespace
                # below as well.
                #
                # An old version stripped whitespace in this spot instead, but
                # that leads to some redundancy and would cause
                # _id_keyword_match to be tried against just "\n" fairly often
                # (because file.readlines() keeps newlines).

                c = s[i]
                i += 1

                if c in "\"'":
                    # String literal/constant symbol
                    if "\\" not in s:
                        # Fast path: If the string contains no backslashes, we
                        # can just find the matching quote.
                        end = s.find(c, i)
                        if end == -1:
                            _tokenization_error(s, filename, linenr)
                        token = s[i:end]
                        i = end + 1
                    else:
                        # Slow path: This could probably be sped up, but it's a
                        # very unusual case anyway.
                        quote = c
                        val = ""
                        while 1:
                            if i >= len(s):
                                _tokenization_error(s, filename, linenr)
                            c = s[i]
                            if c == quote:
                                break
                            if c == "\\":
                                if i + 1 >= len(s):
                                    _tokenization_error(s, filename, linenr)
                                val += s[i + 1]
                                i += 2
                            else:
                                val += c
                                i += 1
                        i += 1
                        token = val

                elif c == "&":
                    # Invalid characters are ignored
                    if i >= len(s) or s[i] != "&": continue
                    token = _T_AND
                    i += 1

                elif c == "|":
                    # Invalid characters are ignored
                    if i >= len(s) or s[i] != "|": continue
                    token = _T_OR
                    i += 1

                elif c == "!":
                    if i < len(s) and s[i] == "=":
                        token = _T_UNEQUAL
                        i += 1
                    else:
                        token = _T_NOT

                elif c == "=":
                    token = _T_EQUAL

                elif c == "(":
                    token = _T_OPEN_PAREN

                elif c == ")":
                    token = _T_CLOSE_PAREN

                elif c == "#": break # Comment

                # Very rare
                elif c == "<":
                    if i < len(s) and s[i] == "=":
                        token = _T_LESS_EQUAL
                        i += 1
                    else:
                        token = _T_LESS

                # Very rare
                elif c == ">":
                    if i < len(s) and s[i] == "=":
                        token = _T_GREATER_EQUAL
                        i += 1
                    else:
                        token = _T_GREATER

                else:
                    # Invalid characters are ignored
                    continue

                # Skip trailing whitespace
                while i < len(s) and s[i].isspace():
                    i += 1

            tokens.append(token)

        return _Feed(tokens)

    def _lookup_sym(self, name, for_eval=False):
        """Fetches the symbol 'name' from the symbol table, creating and
        registering it if it does not exist. If 'for_eval' is True, the symbol
        won't be added to the symbol table if it does not exist -- this is for
        Config.eval()."""
        if name in self._syms:
            return self._syms[name]

        new_sym = Symbol()
        new_sym._config = self
        new_sym._name = name
        if for_eval:
            self._warn("no symbol {} in configuration".format(name))
        else:
            self._syms[name] = new_sym
        return new_sym

    #
    # Expression evaluation
    #

    def _eval_expr(self, expr):
        """Evaluates an expression to "n", "m", or "y"."""

        # Handles e.g. an "x if y" condition where the "if y" part is missing.
        if expr is None:
            return "y"

        res = self._eval_expr_rec(expr)
        if res == "m":
            # Promote "m" to "y" if we're running without modules.
            #
            # Internally, "m" is often rewritten to "m" && MODULES by both the
            # C implementation and Kconfiglib, which takes care of cases where
            # "m" should be demoted to "n" instead.
            modules_sym = self._syms.get("MODULES")
            if modules_sym is None or modules_sym.get_value() != "y":
                return "y"
        return res

    def _eval_expr_rec(self, expr):
        if isinstance(expr, Symbol):
            # Non-bool/tristate symbols are always "n" in a tristate sense,
            # regardless of their value
            if expr._type != BOOL and expr._type != TRISTATE:
                return "n"
            return expr.get_value()

        if isinstance(expr, str):
            return expr if expr in ("m", "y") else "n"

        if expr[0] == _AND:
            ev1 = self._eval_expr_rec(expr[1])
            if ev1 == "n":
                return "n"
            ev2 = self._eval_expr_rec(expr[2])
            return ev2 if ev1 == "y" else \
                   "m" if ev2 != "n" else \
                   "n"

        if expr[0] == _NOT:
            ev = self._eval_expr_rec(expr[1])
            return "n" if ev == "y" else \
                   "y" if ev == "n" else \
                   "m"

        if expr[0] == _OR:
            ev1 = self._eval_expr_rec(expr[1])
            if ev1 == "y":
                return "y"
            ev2 = self._eval_expr_rec(expr[2])
            return ev2 if ev1 == "n" else \
                   "y" if ev2 == "y" else \
                   "m"

        if expr[0] in _RELATIONS:
            # Implements <, <=, >, >= comparisons as well. These were added to
            # kconfig in 31847b67 (kconfig: allow use of relations other than
            # (in)equality).

            # This mirrors the C implementation pretty closely. Perhaps there's
            # a more pythonic way to structure this.

            oper, op1, op2 = expr
            op1_type, op1_str = _type_and_val(op1)
            op2_type, op2_str = _type_and_val(op2)

            # If both operands are strings...
            if op1_type == STRING and op2_type == STRING:
                # ...then compare them lexicographically
                comp = _strcmp(op1_str, op2_str)
            else:
                # Otherwise, try to compare them as numbers
                try:
                    comp = int(op1_str, _TYPE_TO_BASE[op1_type]) - \
                           int(op2_str, _TYPE_TO_BASE[op2_type])
                except ValueError:
                    # They're not both valid numbers. If the comparison is
                    # anything but = or !=, return 'n'. Otherwise, reuse
                    # _strcmp() to check for (in)equality.
                    if oper not in (_EQUAL, _UNEQUAL):
                        return "n"
                    comp = _strcmp(op1_str, op2_str)

            if   oper == _EQUAL:         res = comp == 0
            elif oper == _UNEQUAL:       res = comp != 0
            elif oper == _LESS:          res = comp < 0
            elif oper == _LESS_EQUAL:    res = comp <= 0
            elif oper == _GREATER:       res = comp > 0
            elif oper == _GREATER_EQUAL: res = comp >= 0

            return "y" if res else "n"

        _internal_error("Internal error while evaluating expression: "
                        "unknown operation {}.".format(expr[0]))

    def _eval_min(self, e1, e2):
        """Returns the minimum value of the two expressions. Equates None with
        'y'."""
        e1_eval = self._eval_expr(e1)
        e2_eval = self._eval_expr(e2)
        return e1_eval if tri_less(e1_eval, e2_eval) else e2_eval

    def _eval_max(self, e1, e2):
        """Returns the maximum value of the two expressions. Equates None with
        'y'."""
        e1_eval = self._eval_expr(e1)
        e2_eval = self._eval_expr(e2)
        return e1_eval if tri_greater(e1_eval, e2_eval) else e2_eval

    #
    # Dependency tracking (for caching and invalidation)
    #

    def _build_dep(self):
        """Populates the Symbol._dep sets, linking the symbol to the symbols
        that immediately depend on it in the sense that changing the value of
        the symbol might affect the values of those other symbols. This is used
        for caching/invalidation purposes. The calculated sets might be larger
        than necessary as we don't do any complicated analysis of the
        expressions."""

        # Adds 'sym' as a directly dependent symbol to all symbols that appear
        # in the expression 'e'
        def add_expr_deps(expr, sym):
            res = []
            _expr_syms(expr, res)
            for expr_sym in res:
                expr_sym._dep.add(sym)

        # The directly dependent symbols of a symbol are:
        #  - Any symbols whose prompts, default values, _rev_dep (select
        #    condition), _weak_rev_dep (imply condition) or ranges depend on
        #    the symbol
        #  - Any symbols that belong to the same choice statement as the symbol
        #    (these won't be included in _dep as that makes the dependency
        #    graph unwieldy, but Symbol._get_dependent() will include them)
        #  - Any symbols in a choice statement that depends on the symbol

        # Only calculate _dep for defined symbols. Undefined symbols could
        # theoretically be selected/implied, but it wouldn't change their value
        # (they always evaluate to their name), so it's not a true dependency.

        for sym in self._defined_syms:
            for _, e in sym._prompts:
                add_expr_deps(e, sym)

            for v, e in sym._def_exprs:
                add_expr_deps(v, sym)
                add_expr_deps(e, sym)

            add_expr_deps(sym._rev_dep, sym)
            add_expr_deps(sym._weak_rev_dep, sym)

            for l, u, e in sym._ranges:
                add_expr_deps(l, sym)
                add_expr_deps(u, sym)
                add_expr_deps(e, sym)

            if sym._is_choice_sym:
                choice = sym._parent
                for _, e in choice._prompts:
                    add_expr_deps(e, sym)
                for _, e in choice._def_exprs:
                    add_expr_deps(e, sym)

    def _eq_to_sym(self, eq):
        """_expr_depends_on() helper. For (in)equalities of the form sym = y/m
        or sym != n, returns sym. For other (in)equalities, returns None."""
        relation, left, right = eq

        def transform_y_m_n(item):
            if item is self._y: return "y"
            if item is self._m: return "m"
            if item is self._n: return "n"
            return item

        left = transform_y_m_n(left)
        right = transform_y_m_n(right)

        # Make sure the symbol (if any) appears to the left
        if not isinstance(left, Symbol):
            left, right = right, left
        if not isinstance(left, Symbol):
            return None
        if (relation == _EQUAL and right in ("m", "y")) or \
           (relation == _UNEQUAL and right == "n"):
            return left
        return None

    def _expr_depends_on(self, expr, sym):
        """Reimplementation of expr_depends_symbol() from mconf.c. Used to
        determine if a submenu should be implicitly created, which influences
        what items inside choice statements are considered choice items."""
        if expr is None:
            return False

        def rec(expr):
            if isinstance(expr, str):
                return False
            if isinstance(expr, Symbol):
                return expr is sym

            if expr[0] in (_EQUAL, _UNEQUAL):
                return self._eq_to_sym(expr) is sym
            if expr[0] == _AND:
                return rec(expr[1]) or rec(expr[2])
            return False

        return rec(expr)

    def _invalidate_all(self):
        # Undefined symbols never change value and don't need to be
        # invalidated, so we can just iterate over defined symbols
        for sym in self._defined_syms:
            sym._invalidate()

    #
    # Printing and misc.
    #

    def _expand_sym_refs(self, s):
        """Expands $-references to symbols in 's' to symbol values, or to the
        empty string for undefined symbols."""

        while 1:
            sym_ref_match = _sym_ref_re_search(s)
            if sym_ref_match is None:
                return s

            sym_name = sym_ref_match.group(0)[1:]
            sym = self._syms.get(sym_name)
            expansion = "" if sym is None else sym.get_value()

            s = s[:sym_ref_match.start()] + \
                expansion + \
                s[sym_ref_match.end():]

    def _expr_val_str(self, expr, no_value_str="(none)",
                      get_val_instead_of_eval=False):
        """Printing helper. Returns a string with 'expr' and its value.

        no_value_str: String to return when 'expr' is missing (None).

        get_val_instead_of_eval: Assume 'expr' is a symbol or string (constant
          symbol) and get its value directly instead of evaluating it to a
          tristate value."""

        if expr is None:
            return no_value_str

        if get_val_instead_of_eval:
            if isinstance(expr, str):
                return _expr_to_str(expr)
            val = expr.get_value()
        else:
            val = self._eval_expr(expr)

        return "{} (value: {})".format(_expr_to_str(expr), _expr_to_str(val))

    def _get_sym_or_choice_str(self, sc):
        """Symbols and choices have many properties in common, so we factor out
        common __str__() stuff here. "sc" is short for "symbol or choice"."""

        # As we deal a lot with string representations here, use some
        # convenient shorthand:
        s = _expr_to_str

        #
        # Common symbol/choice properties
        #

        user_val_str = "(no user value)" if sc._user_val is None else \
                       s(sc._user_val)

        # Build prompts string
        if not sc._prompts:
            prompts_str = " (no prompts)"
        else:
            prompts_str_rows = []
            for prompt, cond_expr in sc._orig_prompts:
                prompts_str_rows.append(
                    ' "{}"'.format(prompt)
                    if cond_expr is None else
                    ' "{}" if {}'.format(prompt,
                                         self._expr_val_str(cond_expr)))
            prompts_str = "\n".join(prompts_str_rows)

        # Build locations string
        locations_str = "(no locations)" \
                        if not sc._def_locations else \
                        " ".join(["{}:{}".format(filename, linenr)
                                  for filename, linenr in sc._def_locations])

        # Build additional-dependencies-from-menus-and-ifs string
        additional_deps_str = " " + \
          self._expr_val_str(sc._deps_from_containing,
                             "(no additional dependencies)")

        #
        # Symbol-specific stuff
        #

        if isinstance(sc, Symbol):
            # Build ranges string
            if isinstance(sc, Symbol):
                if not sc._orig_ranges:
                    ranges_str = " (no ranges)"
                else:
                    ranges_str_rows = []
                    for l, u, cond_expr in sc._orig_ranges:
                        ranges_str_rows.append(
                            " [{}, {}]".format(s(l), s(u))
                            if cond_expr is None else
                            " [{}, {}] if {}"
                            .format(s(l), s(u), self._expr_val_str(cond_expr)))
                    ranges_str = "\n".join(ranges_str_rows)

            # Build default values string
            if not sc._orig_def_exprs:
                defaults_str = " (no default values)"
            else:
                defaults_str_rows = []
                for val_expr, cond_expr in sc._orig_def_exprs:
                    row_str = " " + self._expr_val_str(val_expr, "(none)",
                                                       sc._type == STRING)
                    defaults_str_rows.append(row_str)
                    defaults_str_rows.append("  Condition: " +
                                             self._expr_val_str(cond_expr))
                defaults_str = "\n".join(defaults_str_rows)

            # Build selects string
            if not sc._orig_selects:
                selects_str = " (no selects)"
            else:
                selects_str_rows = []
                for target, cond_expr in sc._orig_selects:
                    selects_str_rows.append(
                        " " + target._name
                        if cond_expr is None else
                        " {} if {}".format(target._name,
                                           self._expr_val_str(cond_expr)))
                selects_str = "\n".join(selects_str_rows)

            # Build implies string
            if not sc._orig_implies:
                implies_str = " (no implies)"
            else:
                implies_str_rows = []
                for target, cond_expr in sc._orig_implies:
                    implies_str_rows.append(
                        " " + target._name
                        if cond_expr is None else
                        " {} if {}".format(target._name,
                                           self._expr_val_str(cond_expr)))
                implies_str = "\n".join(implies_str_rows)

            res = _lines("Symbol " +
                         ("(no name)" if sc._name is None else sc._name),
                         "Type           : " + _TYPENAME[sc._type],
                         "Value          : " + s(sc.get_value()),
                         "User value     : " + user_val_str,
                         "Visibility     : " + s(_get_visibility(sc)),
                         "Is choice item : " + str(sc._is_choice_sym),
                         "Is defined     : " + str(sc._is_defined),
                         "Is from env.   : " + str(sc._is_from_env),
                         "Is special     : " + str(sc._is_special),
                         "")
            if sc._ranges:
                res += _lines("Ranges:", ranges_str + "\n")
            res += _lines("Prompts:",
                          prompts_str,
                          "Default values:",
                          defaults_str,
                          "Selects:",
                          selects_str,
                          "Implies:",
                          implies_str,
                          "Reverse (select-related) dependencies:",
                          " (no reverse dependencies)"
                          if sc._rev_dep == "n"
                          else " " + self._expr_val_str(sc._rev_dep),
                          "Weak reverse (imply-related) dependencies:",
                          " (no weak reverse dependencies)"
                          if sc._weak_rev_dep == "n"
                          else " " + self._expr_val_str(sc._weak_rev_dep),
                          "Additional dependencies from enclosing menus "
                          "and ifs:",
                          additional_deps_str,
                          "Locations: " + locations_str)

            return res

        #
        # Choice-specific stuff
        #

        # Build selected symbol string
        sel = sc.get_selection()
        sel_str = "(no selection)" if sel is None else sel._name

        # Build default values string
        if not sc._def_exprs:
            defaults_str = " (no default values)"
        else:
            defaults_str_rows = []
            for sym, cond_expr in sc._orig_def_exprs:
                defaults_str_rows.append(
                    " " + sym._name
                    if cond_expr is None else
                    " {} if {}".format(sym._name,
                                       self._expr_val_str(cond_expr)))
            defaults_str = "\n".join(defaults_str_rows)

        # Build contained symbols string
        names = [sym._name for sym in sc._actual_symbols]
        syms_string = " ".join(names) if names else "(empty)"

        return _lines("Choice",
                      "Name (for named choices): " +
                      ("(no name)" if sc._name is None else sc._name),
                      "Type            : " + _TYPENAME[sc._type],
                      "Selected symbol : " + sel_str,
                      "User value      : " + user_val_str,
                      "Mode            : " + s(sc.get_mode()),
                      "Visibility      : " + s(_get_visibility(sc)),
                      "Optional        : " + str(sc._optional),
                      "Prompts:",
                      prompts_str,
                      "Defaults:",
                      defaults_str,
                      "Choice symbols:",
                      " " + syms_string,
                      "Additional dependencies from enclosing menus and ifs:",
                      additional_deps_str,
                      "Locations: " + locations_str)

    def _is_header_line(self, line):
        """Returns True is the line could be part of the initial header in a
        .config file (which is really just another comment, but can be handy
        for storing metadata)."""
        return line is not None and line.startswith("#") and \
               not self._unset_re.match(line)

    #
    # Warnings
    #

    def _warn(self, msg, filename=None, linenr=None):
        """For printing general warnings."""
        if self._print_warnings:
            _stderr_msg("warning: " + msg, filename, linenr)

    def _warn_undef_assign(self, msg, filename=None, linenr=None):
        """For printing warnings for assignments to undefined variables. We
        treat this is a separate category of warnings to avoid spamming lots of
        warnings."""
        if self._print_undef_assign:
            _stderr_msg("warning: " + msg, filename, linenr)

    def _warn_undef_assign_load(self, name, val, filename, linenr):
        """Special version for load_config()."""
        self._warn_undef_assign(
            'attempt to assign the value "{}" to the undefined symbol {}' \
            .format(val, name), filename, linenr)

class Item(object):

    """Base class for symbols and other Kconfig constructs. Subclasses are
    Symbol, Choice, Menu, and Comment."""

    def is_symbol(self):
        """Returns True if the item is a symbol. Short for
        isinstance(item, kconfiglib.Symbol)."""
        return isinstance(self, Symbol)

    def is_choice(self):
        """Returns True if the item is a choice. Short for
        isinstance(item, kconfiglib.Choice)."""
        return isinstance(self, Choice)

    def is_menu(self):
        """Returns True if the item is a menu. Short for
        isinstance(item, kconfiglib.Menu)."""
        return isinstance(self, Menu)

    def is_comment(self):
        """Returns True if the item is a comment. Short for
        isinstance(item, kconfiglib.Comment)."""
        return isinstance(self, Comment)

class Symbol(Item):

    """Represents a configuration symbol - e.g. FOO for

    config FOO
        ..."""

    #
    # Public interface
    #

    def get_config(self):
        """Returns the Config instance this symbol is from."""
        return self._config

    def get_name(self):
        """Returns the name of the symbol."""
        return self._name

    def get_type(self):
        """Returns the type of the symbol: one of UNKNOWN, BOOL, TRISTATE,
        STRING, HEX, or INT. These are defined at the top level of the module,
        so you'd do something like

        if sym.get_type() == kconfiglib.STRING:
            ..."""
        return self._type

    def get_prompts(self):
        """Returns a list of prompts defined for the symbol, in the order they
        appear in the configuration files. Returns the empty list for symbols
        with no prompt.

        This list will have a single entry for the vast majority of symbols
        having prompts, but having multiple prompts for a single symbol is
        possible through having multiple 'config' entries for it."""
        return [prompt for prompt, _ in self._orig_prompts]

    def get_help(self):
        """Returns the help text of the symbol, or None if the symbol has no
        help text."""
        return self._help

    def get_parent(self):
        """Returns the menu or choice statement that contains the symbol, or
        None if the symbol is at the top level. Note that if statements are
        treated as syntactic and do not have an explicit class
        representation."""
        return self._parent

    def get_def_locations(self):
        """Returns a list of (filename, linenr) tuples, where filename (string)
        and linenr (int) represent a location where the symbol is defined. For
        the vast majority of symbols this list will only contain one element.
        For the following Kconfig, FOO would get two entries: the lines marked
        with *.

        config FOO *
            bool "foo prompt 1"

        config FOO *
            bool "foo prompt 2"
        """
        return self._def_locations

    def get_ref_locations(self):
        """Returns a list of (filename, linenr) tuples, where filename (string)
        and linenr (int) represent a location where the symbol is referenced in
        the configuration. For example, the lines marked by * would be included
        for FOO below:

        config A
            bool
            default BAR || FOO *

        config B
            tristate
            depends on FOO *
            default m if FOO *

        if FOO *
            config A
                bool "A"
        endif

        config FOO (definition not included)
            bool
        """
        return self._ref_locations

    def get_value(self):
        """Calculate and return the value of the symbol. See also
        Symbol.set_user_value()."""

        if self._cached_val is not None:
            return self._cached_val

        # As a quirk of Kconfig, undefined symbols get their name as their
        # value. This is why things like "FOO = bar" work for seeing if FOO has
        # the value "bar".
        if self._type == UNKNOWN:
            self._cached_val = self._name
            return self._name

        # This will hold the value at the end of the function
        val = _DEFAULT_VALUE[self._type]

        vis = _get_visibility(self)

        if self._type in (BOOL, TRISTATE):
            if not self._is_choice_sym:
                self._write_to_conf = (vis != "n")

                if vis != "n" and self._user_val is not None:
                    # If the symbol is visible and has a user value, we use
                    # that
                    val = self._config._eval_min(self._user_val, vis)

                else:
                    # Otherwise, we look at defaults and weak reverse
                    # dependencies (implies)

                    for def_expr, cond_expr in self._def_exprs:
                        cond_val = self._config._eval_expr(cond_expr)
                        if cond_val != "n":
                            self._write_to_conf = True
                            val = self._config._eval_min(def_expr, cond_val)
                            break

                    weak_rev_dep_val = \
                        self._config._eval_expr(self._weak_rev_dep)
                    if weak_rev_dep_val != "n":
                        self._write_to_conf = True
                        val = self._config._eval_max(val, weak_rev_dep_val)

                # Reverse (select-related) dependencies take precedence
                rev_dep_val = self._config._eval_expr(self._rev_dep)
                if rev_dep_val != "n":
                    self._write_to_conf = True
                    val = self._config._eval_max(val, rev_dep_val)

            else:
                # (bool/tristate) symbol in choice. See _get_visibility() for
                # more choice-related logic.

                # Initially
                self._write_to_conf = False

                if vis != "n":
                    choice = self._parent
                    mode = choice.get_mode()

                    if mode != "n":
                        self._write_to_conf = True

                        if mode == "y":
                            val = "y" if choice.get_selection() is self \
                                  else "n"
                        elif self._user_val in ("m", "y"):
                            # mode == "m" here
                            val = "m"

            # We need to promote "m" to "y" in two circumstances:
            #  1) If our type is boolean
            #  2) If our _weak_rev_dep (from IMPLY) is "y"
            if val == "m" and \
               (self._type == BOOL or
                self._config._eval_expr(self._weak_rev_dep) == "y"):
                val = "y"

        elif self._type in (INT, HEX):
            base = _TYPE_TO_BASE[self._type]

            # Check if a range is in effect
            for low_expr, high_expr, cond_expr in self._ranges:
                if self._config._eval_expr(cond_expr) != "n":
                    has_active_range = True

                    low_str = _str_val(low_expr)
                    high_str = _str_val(high_expr)

                    low = int(low_str, base) if \
                      _is_base_n(low_str, base) else 0
                    high = int(high_str, base) if \
                      _is_base_n(high_str, base) else 0

                    break
            else:
                has_active_range = False

            self._write_to_conf = (vis != "n")

            if vis != "n" and self._user_val is not None and \
               _is_base_n(self._user_val, base) and \
               (not has_active_range or
                low <= int(self._user_val, base) <= high):

                # If the user value is well-formed and satisfies range
                # contraints, it is stored in exactly the same form as
                # specified in the assignment (with or without "0x", etc.)
                val = self._user_val

            else:
                # No user value or invalid user value. Look at defaults.

                for val_expr, cond_expr in self._def_exprs:
                    if self._config._eval_expr(cond_expr) != "n":
                        self._write_to_conf = True

                        # Similarly to above, well-formed defaults are
                        # preserved as is. Defaults that do not satisfy a range
                        # constraints are clamped and take on a standard form.

                        val = _str_val(val_expr)

                        if _is_base_n(val, base):
                            val_num = int(val, base)
                            if has_active_range:
                                clamped_val = None

                                if val_num < low:
                                    clamped_val = low
                                elif val_num > high:
                                    clamped_val = high

                                if clamped_val is not None:
                                    val = (hex(clamped_val)
                                           if self._type == HEX else
                                           str(clamped_val))

                            break

                else:
                    # No default kicked in. If there is an active range
                    # constraint, then the low end of the range is used,
                    # provided it's > 0, with "0x" prepended as appropriate.
                    if has_active_range and low > 0:
                        val = (hex(low) if self._type == HEX else str(low))

        elif self._type == STRING:
            self._write_to_conf = (vis != "n")

            if vis != "n" and self._user_val is not None:
                val = self._user_val
            else:
                for val_expr, cond_expr in self._def_exprs:
                    if self._config._eval_expr(cond_expr) != "n":
                        self._write_to_conf = True
                        val = _str_val(val_expr)
                        break

        self._cached_val = val
        return val

    def get_user_value(self):
        """Returns the value assigned to the symbol in a .config or via
        Symbol.set_user_value() (provided the value was valid for the type of
        the symbol). Returns None in case of no user value."""
        return self._user_val

    def get_upper_bound(self):
        """For string/hex/int symbols and for bool and tristate symbols that
        cannot be modified (see is_modifiable()), returns None.

        Otherwise, returns the highest value the symbol can be set to with
        Symbol.set_user_value() (that will not be truncated): one of "m" or
        "y", arranged from lowest to highest. This corresponds to the highest
        value the symbol could be given in e.g. the 'make menuconfig'
        interface.

        See also the tri_less*() and tri_greater*() functions, which could come
        in handy."""
        if self._type != BOOL and self._type != TRISTATE:
            return None
        rev_dep_val = self._config._eval_expr(self._rev_dep)
        # A bool selected to "m" gets promoted to "y", pinning it
        if rev_dep_val == "m" and self._type == BOOL:
            return None
        vis = _get_visibility(self)
        return vis if tri_greater(vis, rev_dep_val) else None

    def get_lower_bound(self):
        """For string/hex/int symbols and for bool and tristate symbols that
        cannot be modified (see is_modifiable()), returns None.

        Otherwise, returns the lowest value the symbol can be set to with
        Symbol.set_user_value() (that will not be truncated): one of "n" or
        "m", arranged from lowest to highest. This corresponds to the lowest
        value the symbol could be given in e.g. the 'make menuconfig'
        interface.

        See also the tri_less*() and tri_greater*() functions, which could come
        in handy."""
        if self._type != BOOL and self._type != TRISTATE:
            return None
        rev_dep_val = self._config._eval_expr(self._rev_dep)
        # A bool selected to "m" gets promoted to "y", pinning it
        if rev_dep_val == "m" and self._type == BOOL:
            return None
        return rev_dep_val if tri_greater(_get_visibility(self), rev_dep_val) \
               else None

    def get_assignable_values(self):
        """For string/hex/int symbols and for bool and tristate symbols that
        cannot be modified (see is_modifiable()), returns the empty list.

        Otherwise, returns a list containing the user values that can be
        assigned to the symbol (that won't be truncated). Usage example:

        if "m" in sym.get_assignable_values():
            sym.set_user_value("m")

        This is basically a more convenient interface to
        get_lower/upper_bound() when wanting to test if a particular tristate
        value can be assigned."""
        if self._type != BOOL and self._type != TRISTATE:
            return []
        rev_dep_val = self._config._eval_expr(self._rev_dep)
        # A bool selected to "m" gets promoted to "y", pinning it
        if rev_dep_val == "m" and self._type == BOOL:
            return []
        res = ["n", "m", "y"][_TRI_TO_INT[rev_dep_val] :
                              _TRI_TO_INT[_get_visibility(self)] + 1]
        return res if len(res) > 1 else []

    def get_visibility(self):
        """Returns the visibility of the symbol: one of "n", "m" or "y". For
        bool and tristate symbols, this is an upper bound on the value users
        can set for the symbol. For other types of symbols, a visibility of "n"
        means the user value will be ignored. A visibility of "n" corresponds
        to not being visible in the 'make *config' interfaces.

        Example (assuming we're running with modules enabled -- i.e., MODULES
        set to 'y'):

        # Assume this has been assigned 'n'
        config N_SYM
            tristate "N_SYM"

        # Assume this has been assigned 'm'
        config M_SYM
            tristate "M_SYM"

        # Has visibility 'n'
        config A
            tristate "A"
            depends on N_SYM

        # Has visibility 'm'
        config B
            tristate "B"
            depends on M_SYM

        # Has visibility 'y'
        config C
            tristate "C"

        # Has no prompt, and hence visibility 'n'
        config D
            tristate

        Having visibility be tri-valued ensures that e.g. a symbol cannot be
        set to "y" by the user if it depends on a symbol with value "m", which
        wouldn't be safe.

        You should probably look at get_lower/upper_bound(),
        get_assignable_values() and is_modifiable() before using this."""
        return _get_visibility(self)

    def get_referenced_symbols(self, refs_from_enclosing=False):
        """Returns the set() of all symbols referenced by this item. For
        example, the symbol defined by

        config FOO
            bool
            prompt "foo" if A && B
            default C if D
            depends on E
            select F if G

        references the symbols A through G.

        refs_from_enclosing (default: False): If True, the symbols referenced
           by enclosing menus and ifs will be included in the result."""
        res = []

        for _, cond_expr in self._orig_prompts:
            _expr_syms(cond_expr, res)
        for val_expr, cond_expr in self._orig_def_exprs:
            _expr_syms(val_expr, res)
            _expr_syms(cond_expr, res)
        for sym, cond_expr in self._orig_selects:
            res.append(sym)
            _expr_syms(cond_expr, res)
        for sym, cond_expr in self._orig_implies:
            res.append(sym)
            _expr_syms(cond_expr, res)
        for low, high, cond_expr in self._orig_ranges:
            res.append(low)
            res.append(high)
            _expr_syms(cond_expr, res)

        if refs_from_enclosing:
            _expr_syms(self._deps_from_containing, res)

        # Remove duplicates and return
        return set(res)

    def get_selected_symbols(self):
        """Returns the set() of all symbols X for which this symbol has a
        'select X' or 'select X if Y' (regardless of whether Y is satisfied or
        not). This is a subset of the symbols returned by
        get_referenced_symbols()."""
        return {sym for sym, _ in self._orig_selects}

    def get_implied_symbols(self):
        """Returns the set() of all symbols X for which this symbol has an
        'imply X' or 'imply X if Y' (regardless of whether Y is satisfied or
        not). This is a subset of the symbols returned by
        get_referenced_symbols()."""
        return {sym for sym, _ in self._orig_implies}

    def set_user_value(self, v):
        """Sets the user value of the symbol.

        Equal in effect to assigning the value to the symbol within a .config
        file. Use get_lower/upper_bound() or get_assignable_values() to find
        the range of currently assignable values for bool and tristate symbols;
        setting values outside this range will cause the user value to differ
        from the result of Symbol.get_value() (be truncated). Values that are
        invalid for the type (such as a_bool.set_user_value("foo")) are
        ignored, and a warning is emitted if an attempt is made to assign such
        a value.

        For any type of symbol, is_modifiable() can be used to check if a user
        value will currently have any effect on the symbol, as determined by
        its visibility and range of assignable values. Any value that is valid
        for the type (bool, tristate, etc.) will end up being reflected in
        get_user_value() though, and might have an effect later if conditions
        change. To get rid of the user value, use unset_user_value().

        Any symbols dependent on the symbol are (recursively) invalidated, so
        things will just work with regards to dependencies.

        v: The user value to give to the symbol."""
        self._set_user_value_no_invalidate(v, False)

        if self._name == "MODULES":
            # Changing MODULES has wide-ranging effects
            self._config._invalidate_all()
            return

        self._invalidate()
        self._invalidate_dependent()

    def unset_user_value(self):
        """Resets the user value of the symbol, as if the symbol had never
        gotten a user value via Config.load_config() or
        Symbol.set_user_value()."""
        self._unset_user_value_no_recursive_invalidate()
        self._invalidate_dependent()

    def is_modifiable(self):
        """Returns True if the value of the symbol could be modified by calling
        Symbol.set_user_value().

        For bools and tristates, this corresponds to the symbol being visible
        in the 'make menuconfig' interface and not already being pinned to a
        specific value (e.g. because it is selected by another symbol).

        For strings and numbers, this corresponds to just being visible. (See
        Symbol.get_visibility().)"""
        if self._is_special:
            return False
        if self._type in (BOOL, TRISTATE):
            rev_dep_val = self._config._eval_expr(self._rev_dep)
            # A bool selected to "m" gets promoted to "y", pinning it
            if rev_dep_val == "m" and self._type == BOOL:
                return False
            return tri_greater(_get_visibility(self), rev_dep_val)
        return _get_visibility(self) != "n"

    def is_defined(self):
        """Returns False if the symbol is referred to in the Kconfig but never
        actually defined."""
        return self._is_defined

    def is_special(self):
        """Returns True if the symbol is one of the special symbols n, m, y, or
        UNAME_RELEASE, or gets its value from the environment."""
        return self._is_special

    def is_from_environment(self):
        """Returns True if the symbol gets its value from the environment."""
        return self._is_from_env

    def has_ranges(self):
        """Returns True if the symbol is of type INT or HEX and has ranges that
        limit what values it can take on."""
        return bool(self._ranges)

    def is_choice_symbol(self):
        """Returns True if the symbol is in a choice statement and is an actual
        choice symbol (see Choice.get_symbols())."""
        return self._is_choice_sym

    def is_choice_selection(self):
        """Returns True if the symbol is contained in a choice statement and is
        the selected item. Equivalent to

        sym.is_choice_symbol() and sym.get_parent().get_selection() is sym"""
        return self._is_choice_sym and self._parent.get_selection() is self

    def is_allnoconfig_y(self):
        """Returns True if the symbol has the 'allnoconfig_y' option set."""
        return self._allnoconfig_y

    def __str__(self):
        """Returns a string containing various information about the symbol."""
        return self._config._get_sym_or_choice_str(self)

    #
    # Private methods
    #

    def __init__(self):
        """Symbol constructor -- not intended to be called directly by
        Kconfiglib clients."""

        # These attributes are always set on the instance from outside and
        # don't need defaults:
        #   _config
        #   _name
        #   _already_written

        self._type = UNKNOWN
        self._prompts = []
        self._def_exprs = [] # 'default' properties
        self._ranges = [] # 'range' properties (for int and hex)
        self._help = None # Help text
        self._rev_dep = "n" # Reverse (select-related) dependencies
        self._weak_rev_dep = "n" # Weak reverse (imply-related) dependencies
        self._parent = None

        self._user_val = None # Value set by user

        # Prompts, default values, ranges, selects, and implies without any
        # dependencies from parents propagated to them
        self._orig_prompts = []
        self._orig_def_exprs = []
        self._orig_ranges = []
        self._orig_selects = []
        self._orig_implies = []

        # Dependencies inherited from containing menus and ifs
        self._deps_from_containing = None

        # See comment in _parse_properties()
        self._menu_dep = None

        # See Symbol.get_ref/def_locations().
        self._def_locations = []
        self._ref_locations = []

        # Populated in Config._build_dep() after parsing. Links the symbol to
        # the symbols that immediately depend on it (in a caching/invalidation
        # sense). The total set of dependent symbols for the symbol (the
        # transitive closure) is calculated on an as-needed basis in
        # _get_dependent().
        self._dep = set()

        # Cached values

        # Caches the calculated value
        self._cached_val = None
        # Caches the visibility, which acts as an upper bound on the value
        self._cached_visibility = None
        # Caches the total list of dependent symbols. Calculated in
        # _get_dependent().
        self._cached_deps = None

        # Flags

        # Does the symbol have an entry in the Kconfig file?
        self._is_defined = False
        # Should the symbol get an entry in .config?
        self._write_to_conf = False
        # This is set to True for "actual" choice symbols; see
        # Choice._determine_actual_symbols().
        self._is_choice_sym = False
        # Does the symbol get its value in some special way, e.g. from the
        # environment or by being one of the special symbols n, m, and y? If
        # so, the value is stored in self._cached_val, which is never
        # invalidated.
        self._is_special = False
        # Does the symbol get its value from the environment?
        self._is_from_env = False
        # Does the symbol have the 'allnoconfig_y' option set?
        self._allnoconfig_y = False

    def _invalidate(self):
        if self._is_special:
            # Special symbols never change value and keep their value in
            # _cached_val
            return

        if self._is_choice_sym:
            self._parent._invalidate()

        self._cached_val = None
        self._cached_visibility = None

    def _invalidate_dependent(self):
        for sym in self._get_dependent():
            sym._invalidate()

    def _set_user_value_no_invalidate(self, v, suppress_load_warnings):
        """Like set_user_value(), but does not invalidate any symbols.

        suppress_load_warnings: some warnings are annoying when loading a
           .config that can be helpful when manually invoking set_user_value().
           This flag is set to True to suppress such warnings.

           Perhaps this could be made optional for load_config() instead."""

        if self._is_special:
            if self._is_from_env:
                self._config._warn('attempt to assign the value "{}" to the '
                                   'symbol {}, which gets its value from the '
                                   'environment. Assignment ignored.'
                                   .format(v, self._name))
            else:
                self._config._warn('attempt to assign the value "{}" to the '
                                   'special symbol {}. Assignment ignored.'
                                   .format(v, self._name))
            return

        if not self._is_defined:
            filename, linenr = self._ref_locations[0]
            self._config._warn_undef_assign(
                'attempt to assign the value "{}" to {}, which is referenced '
                "at {}:{} but never defined. Assignment ignored."
                .format(v, self._name, filename, linenr))
            return

        # Check if the value is valid for our type
        if not ((self._type == BOOL     and v in ("n", "y")     ) or
                (self._type == TRISTATE and v in ("n", "m", "y")) or
                (self._type == STRING                           ) or
                (self._type == INT      and _is_base_n(v, 10)   ) or
                (self._type == HEX      and _is_base_n(v, 16)   )):
            self._config._warn('the value "{}" is invalid for {}, which has '
                               "type {}. Assignment ignored."
                               .format(v, self._name, _TYPENAME[self._type]))
            return

        if not self._prompts and not suppress_load_warnings:
            self._config._warn('assigning "{}" to the symbol {} which lacks '
                               'prompts and thus has visibility "n". The '
                               'assignment will have no effect.'
                               .format(v, self._name))

        self._user_val = v

        if self._is_choice_sym and self._type in (BOOL, TRISTATE):
            choice = self._parent
            if v == "y":
                choice._user_val = self
                choice._user_mode = "y"
            elif v == "m":
                choice._user_val = None
                choice._user_mode = "m"

    def _unset_user_value_no_recursive_invalidate(self):
        self._invalidate()
        self._user_val = None

        if self._is_choice_sym:
            self._parent._unset_user_value()

    def _add_config_strings(self, add_fn):
        if self._already_written:
            return

        self._already_written = True

        # Note: _write_to_conf is determined in get_value()
        val = self.get_value()
        if not self._write_to_conf:
            return

        if self._type in (BOOL, TRISTATE):
            add_fn("# {}{} is not set\n".format(self._config._config_prefix,
                                                self._name)
                   if val == "n" else
                   "{}{}={}\n".format(self._config._config_prefix, self._name,
                                      val))

        elif self._type in (INT, HEX):
            add_fn("{}{}={}\n".format(self._config._config_prefix,
                                      self._name, val))

        elif self._type == STRING:
            # Escape \ and "
            add_fn('{}{}="{}"\n'
                   .format(self._config._config_prefix, self._name,
                           val.replace("\\", "\\\\").replace('"', '\\"')))

        else:
            _internal_error("Internal error while creating .config: unknown "
                            'type "{}".'.format(self._type))

    def _get_dependent(self):
        """Returns the set of symbols that should be invalidated if the value
        of the symbol changes, because they might be affected by the change.
        Note that this is an internal API -- it's probably of limited
        usefulness to clients."""
        if self._cached_deps is not None:
            return self._cached_deps

        res = set(self._dep)
        for s in self._dep:
            res |= s._get_dependent()

        if self._is_choice_sym:
            # Choice symbols also depend (recursively) on their siblings. The
            # siblings are not included in _dep to avoid dependency loops.
            for sibling in self._parent._actual_symbols:
                if sibling is not self:
                    res.add(sibling)
                    res |= sibling._dep
                    for s in sibling._dep:
                        res |= s._get_dependent()

        self._cached_deps = res
        return res

    def _has_auto_menu_dep_on(self, on):
        """See Choice._determine_actual_symbols()."""
        if not isinstance(self._parent, Choice):
            _internal_error("Attempt to determine auto menu dependency for "
                            "symbol ouside of choice.")

        if not self._prompts:
            # If we have no prompt, use the menu dependencies instead (what was
            # specified with 'depends on')
            return self._menu_dep is not None and \
                   self._config._expr_depends_on(self._menu_dep, on)

        for _, cond_expr in self._prompts:
            if self._config._expr_depends_on(cond_expr, on):
                return True

        return False

class Menu(Item):

    """Represents a menu statement."""

    #
    # Public interface
    #

    def get_config(self):
        """Return the Config instance this menu is from."""
        return self._config

    def get_title(self):
        """Returns the title text of the menu."""
        return self._title

    def get_parent(self):
        """Returns the menu or choice statement that contains the menu, or
        None if the menu is at the top level. Note that if statements are
        treated as syntactic sugar and do not have an explicit class
        representation."""
        return self._parent

    def get_location(self):
        """Returns the location of the menu as a (filename, linenr) tuple,
        where filename is a string and linenr an int."""
        return (self._filename, self._linenr)

    def get_items(self, recursive=False):
        """Returns a list containing the items (symbols, menus, choice
        statements and comments) in in the menu, in the same order that the
        items appear within the menu.

        recursive (default: False): True if items contained in items within the
           menu should be included recursively (preorder)."""

        if not recursive:
            return self._block

        res = []
        for item in self._block:
            res.append(item)
            if isinstance(item, Menu):
                res.extend(item.get_items(True))
            elif isinstance(item, Choice):
                res.extend(item.get_items())
        return res

    def get_symbols(self, recursive=False):
        """Returns a list containing the symbols in the menu, in the same order
        that they appear within the menu.

        recursive (default: False): True if symbols contained in items within
           the menu should be included recursively."""

        return [item for item in self.get_items(recursive) if
                isinstance(item, Symbol)]

    def get_visibility(self):
        """Returns the visibility of the menu. This also affects the visibility
        of subitems. See also Symbol.get_visibility()."""
        return self._config._eval_expr(self._menu_dep)

    def get_visible_if_visibility(self):
        """Returns the visibility the menu gets from its 'visible if'
        condition. "y" if the menu has no 'visible if' condition."""
        return self._config._eval_expr(self._visible_if_expr)

    def get_referenced_symbols(self, refs_from_enclosing=False):
        """See Symbol.get_referenced_symbols()."""
        res = []

        _expr_syms(self._visible_if_expr, res)
        _expr_syms(self._orig_deps
                   if not refs_from_enclosing else
                   self._menu_dep,
                   res)

        # Remove duplicates and return
        return set(res)

    def __str__(self):
        """Returns a string containing various information about the menu."""
        depends_on_str = self._config._expr_val_str(self._orig_deps,
                                                    "(no dependencies)")
        visible_if_str = self._config._expr_val_str(self._visible_if_expr,
                                                    "(no dependencies)")

        additional_deps_str = " " + \
          self._config._expr_val_str(self._deps_from_containing,
                                     "(no additional dependencies)")

        return _lines("Menu",
                      "Title                     : " + self._title,
                      "'depends on' dependencies : " + depends_on_str,
                      "'visible if' dependencies : " + visible_if_str,
                      "Additional dependencies from enclosing menus and ifs:",
                      additional_deps_str,
                      "Location: {}:{}".format(self._filename, self._linenr))

    #
    # Private methods
    #

    def __init__(self):
        """Menu constructor -- not intended to be called directly by
        Kconfiglib clients."""

        # These attributes are always set on the instance from outside and
        # don't need defaults:
        #   _config
        #   _parent
        #   _filename
        #   _linenr
        #   _title
        #   _deps_from_containing
        #   _menu_dep

        # Dependencies specified with 'visible_if'
        self._visible_if_expr = None

        # Dependency expression without dependencies from enclosing menus and
        # ifs propagated
        self._orig_deps = None

        # Contained items
        self._block = []

    def _add_config_strings(self, add_fn):
        if self._config._eval_expr(self._menu_dep) != "n" and \
           self._config._eval_expr(self._visible_if_expr) != "n":
            add_fn("\n#\n# {}\n#\n".format(self._title))

        for item in self._block:
            item._add_config_strings(add_fn)

class Choice(Item):

    """Represents a choice statement. A choice can be in one of three modes:

    "n" - The choice is not visible and no symbols can be selected.

    "m" - Any number of symbols can be set to "m". The rest will be "n". This
          is safe since potentially conflicting options don't actually get
          compiled into the kernel simultaneously with "m".

    "y" - One symbol will be "y" while the rest are "n".

    Only tristate choices can be in "m" mode, and the visibility of the choice
    is an upper bound on the mode, so that e.g. a choice that depends on a
    symbol with value "m" will be in "m" mode.

    The mode changes automatically when a value is assigned to a symbol within
    the choice.

    See Symbol.get_visibility() too."""

    #
    # Public interface
    #

    def get_config(self):
        """Returns the Config instance this choice is from."""
        return self._config

    def get_name(self):
        """For named choices, returns the name. Returns None for unnamed
        choices. No named choices appear anywhere in the kernel Kconfig files
        as of Linux 3.7.0-rc8."""
        return self._name

    def get_type(self):
        """Returns the type of the choice. See Symbol.get_type()."""
        return self._type

    def get_prompts(self):
        """Returns a list of prompts defined for the choice, in the order they
        appear in the configuration files. Returns the empty list for choices
        with no prompt.

        This list will have a single entry for the vast majority of choices
        having prompts, but having multiple prompts for a single choice is
        possible through having multiple 'choice' entries for it (though I'm
        not sure if that ever happens in practice)."""
        return [prompt for prompt, _ in self._orig_prompts]

    def get_help(self):
        """Returns the help text of the choice, or None if the choice has no
        help text."""
        return self._help

    def get_parent(self):
        """Returns the menu or choice statement that contains the choice, or
        None if the choice is at the top level. Note that if statements are
        treated as syntactic sugar and do not have an explicit class
        representation."""
        return self._parent

    def get_def_locations(self):
        """Returns a list of (filename, linenr) tuples, where filename (string)
        and linenr (int) represent a location where the choice is defined. For
        the vast majority of choices (all of them as of Linux 3.7.0-rc8) this
        list will only contain one element, but its possible for named choices
        to be defined in multiple locations."""
        return self._def_locations

    def get_selection(self):
        """Returns the symbol selected (either by the user or through
        defaults), or None if either no symbol is selected or the mode is not
        "y"."""
        if self._cached_selection is not None:
            if self._cached_selection == _NO_SELECTION:
                return None
            return self._cached_selection

        if self.get_mode() != "y":
            return self._cache_ret(None)

        # User choice available?
        if self._user_val is not None and \
           _get_visibility(self._user_val) == "y":
            return self._cache_ret(self._user_val)

        if self._optional:
            return self._cache_ret(None)

        return self._cache_ret(self.get_selection_from_defaults())

    def get_selection_from_defaults(self):
        """Like Choice.get_selection(), but acts as if no symbol has been
        selected by the user and no 'optional' flag is in effect."""

        # Does any 'default SYM [if <cond>]' property apply?
        for sym, cond_expr in self._def_exprs:
            if (self._config._eval_expr(cond_expr) != "n" and
                # Must be visible too
                _get_visibility(sym) != "n"):
                return sym

        # Otherwise, pick the first visible symbol
        for sym in self._actual_symbols:
            if _get_visibility(sym) != "n":
                return sym

        # Couldn't find a default
        return None

    def get_user_selection(self):
        """If the choice is in "y" mode and has a user-selected symbol, returns
        that symbol. Otherwise, returns None."""
        return self._user_val

    def get_items(self):
        """Gets all items contained in the choice in the same order as within
        the configuration ("items" instead of "symbols" since choices and
        comments might appear within choices. This only happens in one place as
        of Linux 3.7.0-rc8, in drivers/usb/gadget/Kconfig)."""
        return self._block

    def get_symbols(self):
        """Returns a list containing the choice's symbols.

        A quirk (perhaps a bug) of Kconfig is that you can put items within a
        choice that will not be considered members of the choice insofar as
        selection is concerned. This happens for example if one symbol within a
        choice 'depends on' the symbol preceding it, or if you put non-symbol
        items within choices.

        As of Linux 3.7.0-rc8, this seems to be used intentionally in one
        place: drivers/usb/gadget/Kconfig.

        This function returns the "proper" symbols of the choice in the order
        they appear in the choice, excluding such items. If you want all items
        in the choice, use get_items()."""
        return self._actual_symbols

    def get_referenced_symbols(self, refs_from_enclosing=False):
        """See Symbol.get_referenced_symbols()."""
        res = []

        for _, cond_expr in self._orig_prompts:
            _expr_syms(cond_expr, res)
        for val_expr, cond_expr in self._orig_def_exprs:
            _expr_syms(val_expr, res)
            _expr_syms(cond_expr, res)

        if refs_from_enclosing:
            _expr_syms(self._deps_from_containing, res)

        # Remove duplicates and return
        return set(res)

    def get_visibility(self):
        """Returns the visibility of the choice statement: one of "n", "m" or
        "y". This acts as an upper limit on the mode of the choice (though bool
        choices can only have the mode "y"). See the class documentation for an
        explanation of modes."""
        return _get_visibility(self)

    def get_mode(self):
        """Returns the mode of the choice. See the class documentation for
        an explanation of modes."""
        minimum_mode = "n" if self._optional else "m"
        mode = self._user_mode if self._user_mode is not None else minimum_mode
        mode = self._config._eval_min(mode, _get_visibility(self))

        # Promote "m" to "y" for boolean choices
        if mode == "m" and self._type == BOOL:
            return "y"

        return mode

    def is_optional(self):
        """Returns True if the choice has the 'optional' flag set (and so will
        default to "n" mode)."""
        return self._optional

    def __str__(self):
        """Returns a string containing various information about the choice
        statement."""
        return self._config._get_sym_or_choice_str(self)

    #
    # Private methods
    #

    def __init__(self):
        """Choice constructor -- not intended to be called directly by
        Kconfiglib clients."""

        # These attributes are always set on the instance from outside and
        # don't need defaults:
        #   _config
        #   _parent
        #   _deps_from_containing
        #   _actual_symbols (set in _determine_actual_symbols())

        self._name = None # Yes, choices can be named
        self._type = UNKNOWN
        self._prompts = []
        self._def_exprs = [] # 'default' properties
        self._help = None # Help text

        self._user_val = None
        self._user_mode = None

        # The prompts and default values without any dependencies from
        # enclosing menus and ifs propagated
        self._orig_prompts = []
        self._orig_def_exprs = []

        # See Choice.get_def_locations()
        self._def_locations = []

        # Cached values
        self._cached_selection = None
        self._cached_visibility = None

        self._optional = False

        # Contained items
        self._block = []

    def _determine_actual_symbols(self):
        """If a symbol's visibility depends on the preceding symbol within a
        choice, it is no longer viewed as a choice item. (This is quite
        possibly a bug, but some things consciously use it... ugh. It stems
        from automatic submenu creation.) In addition, it's possible to have
        choices and comments within choices, and those shouldn't be considered
        choice items either. Only drivers/usb/gadget/Kconfig seems to depend on
        any of this. This method computes the "actual" items in the choice and
        sets the _is_choice_sym flag on them (retrieved via
        is_choice_symbol()).

        Don't let this scare you: an earlier version simply checked for a
        sequence of symbols where all symbols after the first appeared in the
        'depends on' expression of the first, and that worked fine.  The added
        complexity is to be future-proof in the event that
        drivers/usb/gadget/Kconfig turns even more sinister. It might very well
        be overkilling things (especially if that file is refactored ;)."""

        self._actual_symbols = []

        # Items might depend on each other in a tree structure, so we need a
        # stack to keep track of the current tentative parent
        stack = []

        for item in self._block:
            if not isinstance(item, Symbol):
                stack = []
                continue

            while stack:
                if item._has_auto_menu_dep_on(stack[-1]):
                    # The item should not be viewed as a choice item, so don't
                    # set item._is_choice_sym
                    stack.append(item)
                    break
                else:
                    stack.pop()
            else:
                item._is_choice_sym = True
                self._actual_symbols.append(item)
                stack.append(item)

    def _cache_ret(self, selection):
        # As None is used to indicate the lack of a cached value we can't use
        # that to cache the fact that the choice has no selection. Instead, we
        # use the symbolic constant _NO_SELECTION.
        if selection is None:
            self._cached_selection = _NO_SELECTION
        else:
            self._cached_selection = selection

        return selection

    def _invalidate(self):
        self._cached_selection = None
        self._cached_visibility = None

    def _unset_user_value(self):
        self._invalidate()
        self._user_val = None
        self._user_mode = None

    def _add_config_strings(self, add_fn):
        for item in self._block:
            item._add_config_strings(add_fn)

class Comment(Item):

    """Represents a comment statement."""

    #
    # Public interface
    #

    def get_config(self):
        """Returns the Config instance this comment is from."""
        return self._config

    def get_text(self):
        """Returns the text of the comment."""
        return self._text

    def get_parent(self):
        """Returns the menu or choice statement that contains the comment, or
        None if the comment is at the top level. Note that if statements are
        treated as syntactic sugar and do not have an explicit class
        representation."""
        return self._parent

    def get_location(self):
        """Returns the location of the comment as a (filename, linenr) tuple,
        where filename is a string and linenr an int."""
        return (self._filename, self._linenr)

    def get_visibility(self):
        """Returns the visibility of the comment. See also
        Symbol.get_visibility()."""
        return self._config._eval_expr(self._menu_dep)

    def get_referenced_symbols(self, refs_from_enclosing=False):
        """See Symbol.get_referenced_symbols()."""
        res = []

        _expr_syms(self._orig_deps
                   if not refs_from_enclosing else
                   self._menu_dep,
                   res)

        # Remove duplicates and return
        return set(res)

    def __str__(self):
        """Returns a string containing various information about the
        comment."""
        dep_str = self._config._expr_val_str(self._orig_deps,
                                             "(no dependencies)")

        additional_deps_str = " " + \
          self._config._expr_val_str(self._deps_from_containing,
                                     "(no additional dependencies)")

        return _lines("Comment",
                      "Text: " + self._text,
                      "Dependencies: " + dep_str,
                      "Additional dependencies from enclosing menus and ifs:",
                      additional_deps_str,
                      "Location: {}:{}".format(self._filename, self._linenr))

    #
    # Private methods
    #

    def __init__(self):
        """Comment constructor -- not intended to be called directly by
        Kconfiglib clients."""

        # These attributes are always set on the instance from outside and
        # don't need defaults:
        #   _config
        #   _parent
        #   _filename
        #   _linenr
        #   _text
        #   _deps_from_containing
        #   _menu_dep
        #   _orig_deps

    def _add_config_strings(self, add_fn):
        if self._config._eval_expr(self._menu_dep) != "n":
            add_fn("\n#\n# {}\n#\n".format(self._text))

class Kconfig_Syntax_Error(Exception):
    """Exception raised for syntax errors."""
    pass

class Internal_Error(Exception):
    """Exception raised for internal errors."""
    pass

#
# Public functions
#

def tri_less(v1, v2):
    """Returns True if the tristate v1 is less than the tristate v2, where "n",
    "m" and "y" are ordered from lowest to highest."""
    return _TRI_TO_INT[v1] < _TRI_TO_INT[v2]

def tri_less_eq(v1, v2):
    """Returns True if the tristate v1 is less than or equal to the tristate
    v2, where "n", "m" and "y" are ordered from lowest to highest."""
    return _TRI_TO_INT[v1] <= _TRI_TO_INT[v2]

def tri_greater(v1, v2):
    """Returns True if the tristate v1 is greater than the tristate v2, where
    "n", "m" and "y" are ordered from lowest to highest."""
    return _TRI_TO_INT[v1] > _TRI_TO_INT[v2]

def tri_greater_eq(v1, v2):
    """Returns True if the tristate v1 is greater than or equal to the tristate
    v2, where "n", "m" and "y" are ordered from lowest to highest."""
    return _TRI_TO_INT[v1] >= _TRI_TO_INT[v2]

#
# Internal classes
#

class _Feed(object):

    """Class for working with sequences in a stream-like fashion; handy for
    tokens."""

    # This would be more helpful on the item classes, but would remove some
    # flexibility
    __slots__ = ['items', 'length', 'i']

    def __init__(self, items):
        self.items = items
        self.length = len(self.items)
        self.i = 0

    def get_next(self):
        if self.i >= self.length:
            return None
        item = self.items[self.i]
        self.i += 1
        return item

    def peek_next(self):
        return None if self.i >= self.length else self.items[self.i]

    def check(self, token):
        """Check if the next token is 'token'. If so, remove it from the token
        feed and return True. Otherwise, leave it in and return False."""
        if self.i < self.length and self.items[self.i] == token:
            self.i += 1
            return True
        return False

    def unget_all(self):
        self.i = 0

class _FileFeed(object):

    """Feeds lines from a file. Keeps track of the filename and current line
    number. Joins any line ending in \\ with the following line. We need to be
    careful to get the line number right in the presence of continuation
    lines."""

    __slots__ = ['filename', 'lines', 'length', 'linenr']

    def __init__(self, filename):
        self.filename = filename
        with open(filename) as f:
            # No interleaving of I/O and processing yet. Don't know if it would
            # help.
            self.lines = f.readlines()
        self.length = len(self.lines)
        self.linenr = 0

    def get_next(self):
        if self.linenr >= self.length:
            return None
        line = self.lines[self.linenr]
        self.linenr += 1
        while line.endswith("\\\n"):
            line = line[:-2] + self.lines[self.linenr]
            self.linenr += 1
        return line

    def peek_next(self):
        linenr = self.linenr
        if linenr >= self.length:
            return None
        line = self.lines[linenr]
        while line.endswith("\\\n"):
            linenr += 1
            line = line[:-2] + self.lines[linenr]
        return line

    def unget(self):
        self.linenr -= 1
        while self.lines[self.linenr].endswith("\\\n"):
            self.linenr -= 1

    def next_nonblank(self):
        """Removes lines up to and including the next non-blank (not all-space)
        line and returns it. Returns None if there are no more non-blank
        lines."""
        while 1:
            line = self.get_next()
            if line is None or not line.isspace():
                return line

#
# Internal functions
#

def _get_visibility(sc):
    """Symbols and Choices have a "visibility" that acts as an upper bound on
    the values a user can set for them, corresponding to the visibility in e.g.
    'make menuconfig'. This function calculates the visibility for the Symbol
    or Choice 'sc' -- the logic is nearly identical."""
    if sc._cached_visibility is None:
        vis = "n"
        for _, cond_expr in sc._prompts:
            vis = sc._config._eval_max(vis, cond_expr)

        if isinstance(sc, Symbol) and sc._is_choice_sym:
            choice = sc._parent
            if choice._type == TRISTATE and sc._type != TRISTATE and \
               choice.get_mode() != "y":
                # Non-tristate choice symbols in tristate choices depend on the
                # choice being in mode "y"
                vis = "n"
            elif sc._type == TRISTATE and vis == "m" and \
                 choice.get_mode() == "y":
                # Choice symbols with visibility "m" are not visible if the
                # choice has mode "y"
                vis = "n"
            else:
                vis = sc._config._eval_min(vis, _get_visibility(choice))

        # Promote "m" to "y" if we're dealing with a non-tristate
        if vis == "m" and sc._type != TRISTATE:
            vis = "y"

        sc._cached_visibility = vis

    return sc._cached_visibility

def _make_and(e1, e2):
    """Constructs an _AND (&&) expression. Performs trivial simplification.
    Nones equate to 'y'.

    Returns None if e1 == e2 == None, so that ANDing two nonexistent
    expressions gives a nonexistent expression."""
    if e1 is None or e1 == "y":
        return e2
    if e2 is None or e2 == "y":
        return e1
    return (_AND, e1, e2)

def _make_or(e1, e2):
    """Constructs an _OR (||) expression. Performs trivial simplification and
    avoids Nones. Nones equate to 'y', which is usually what we want, but needs
    to be kept in mind."""

    # Perform trivial simplification and avoid None's (which
    # correspond to y's)
    if e1 is None or e2 is None or e1 == "y" or e2 == "y":
        return "y"
    if e1 == "n":
        return e2
    return (_OR, e1, e2)

def _expr_syms_rec(expr, res):
    """_expr_syms() helper. Recurses through expressions."""
    if isinstance(expr, Symbol):
        res.append(expr)
    elif isinstance(expr, str):
        return
    elif expr[0] in (_AND, _OR):
        _expr_syms_rec(expr[1], res)
        _expr_syms_rec(expr[2], res)
    elif expr[0] == _NOT:
        _expr_syms_rec(expr[1], res)
    elif expr[0] in _RELATIONS:
        if isinstance(expr[1], Symbol):
            res.append(expr[1])
        if isinstance(expr[2], Symbol):
            res.append(expr[2])
    else:
        _internal_error("Internal error while fetching symbols from an "
                        "expression with token stream {}.".format(expr))

def _expr_syms(expr, res):
    """append()s the symbols in 'expr' to 'res'. Does not remove duplicates."""
    if expr is not None:
        _expr_syms_rec(expr, res)

def _str_val(obj):
    """Returns the value of obj as a string. If obj is not a string (constant
    symbol), it must be a Symbol."""
    return obj if isinstance(obj, str) else obj.get_value()

def _format_and_op(expr):
    """_expr_to_str() helper. Returns the string representation of 'expr',
    which is assumed to be an operand to _AND, with parentheses added if
    needed."""
    if isinstance(expr, tuple) and expr[0] == _OR:
        return "({})".format(_expr_to_str(expr))
    return _expr_to_str(expr)

def _expr_to_str(expr):
    if isinstance(expr, str):
        return '"{}"'.format(expr)

    if isinstance(expr, Symbol):
        return expr._name

    if expr[0] == _NOT:
        if isinstance(expr[1], (str, Symbol)):
            return "!" + _expr_to_str(expr[1])
        return "!({})".format(_expr_to_str(expr[1]))

    if expr[0] == _AND:
        return "{} && {}".format(_format_and_op(expr[1]),
                                 _format_and_op(expr[2]))

    if expr[0] == _OR:
        return "{} || {}".format(_expr_to_str(expr[1]),
                                 _expr_to_str(expr[2]))

    # Relation
    return "{} {} {}".format(_expr_to_str(expr[1]),
                             _RELATION_TO_STR[expr[0]],
                             _expr_to_str(expr[2]))

def _type_and_val(obj):
    """Helper to hack around the fact that we don't represent plain strings as
    Symbols. Takes either a plain string or a Symbol and returns a
    (<type>, <value>) tuple."""
    if isinstance(obj, str):
        return (STRING, obj)
    return (obj._type, obj.get_value())

def _indentation(line):
    """Returns the length of the line's leading whitespace, treating tab stops
    as being spaced 8 characters apart."""
    line = line.expandtabs()
    return len(line) - len(line.lstrip())

def _deindent(line, indent):
    """Deindent 'line' by 'indent' spaces."""
    line = line.expandtabs()
    if len(line) <= indent:
        return line
    return line[indent:]

def _is_base_n(s, n):
    try:
        int(s, n)
        return True
    except ValueError:
        return False

def _strcmp(s1, s2):
    """strcmp()-alike that returns -1, 0, or 1."""
    return (s1 > s2) - (s1 < s2)

def _lines(*args):
    """Returns a string consisting of all arguments, with newlines inserted
    between them."""
    return "\n".join(args)

def _stderr_msg(msg, filename, linenr):
    if filename is not None:
        sys.stderr.write("{}:{}: ".format(filename, linenr))
    sys.stderr.write(msg + "\n")

def _tokenization_error(s, filename, linenr):
    loc = "" if filename is None else "{}:{}: ".format(filename, linenr)
    raise Kconfig_Syntax_Error("{}Couldn't tokenize '{}'"
                               .format(loc, s.strip()))

def _parse_error(s, msg, filename, linenr):
    loc = "" if filename is None else "{}:{}: ".format(filename, linenr)
    raise Kconfig_Syntax_Error("{}Couldn't parse '{}'{}"
                               .format(loc, s.strip(),
                                       "." if msg is None else ": " + msg))

def _internal_error(msg):
    raise Internal_Error(
        msg +
        "\nSorry! You may want to send an email to ulfalizer a.t Google's "
        "email service to tell me about this. Include the message above and "
        "the stack trace and describe what you were doing.")

#
# Public global constants
#

# Integers representing symbol types
(
    BOOL,
    HEX,
    INT,
    STRING,
    TRISTATE,
    UNKNOWN
) = range(6)

#
# Internal global constants
#

# Tokens
(
    _T_ALLNOCONFIG_Y,
    _T_AND,
    _T_BOOL,
    _T_CHOICE,
    _T_CLOSE_PAREN,
    _T_COMMENT,
    _T_CONFIG,
    _T_DEFAULT,
    _T_DEFCONFIG_LIST,
    _T_DEF_BOOL,
    _T_DEF_TRISTATE,
    _T_DEPENDS,
    _T_ENDCHOICE,
    _T_ENDIF,
    _T_ENDMENU,
    _T_ENV,
    _T_EQUAL,
    _T_GREATER,
    _T_GREATER_EQUAL,
    _T_HELP,
    _T_HEX,
    _T_IF,
    _T_IMPLY,
    _T_INT,
    _T_LESS,
    _T_LESS_EQUAL,
    _T_MAINMENU,
    _T_MENU,
    _T_MODULES,
    _T_NOT,
    _T_ON,
    _T_OPEN_PAREN,
    _T_OPTION,
    _T_OPTIONAL,
    _T_OR,
    _T_PROMPT,
    _T_RANGE,
    _T_SELECT,
    _T_SOURCE,
    _T_STRING,
    _T_TRISTATE,
    _T_UNEQUAL,
    _T_VISIBLE,
) = range(43)

# Keyword to token map. Note that the get() method is assigned directly as a
# small optimization.
_get_keyword = {
    "allnoconfig_y":  _T_ALLNOCONFIG_Y,
    "bool":           _T_BOOL,
    "boolean":        _T_BOOL,
    "choice":         _T_CHOICE,
    "comment":        _T_COMMENT,
    "config":         _T_CONFIG,
    "def_bool":       _T_DEF_BOOL,
    "def_tristate":   _T_DEF_TRISTATE,
    "default":        _T_DEFAULT,
    "defconfig_list": _T_DEFCONFIG_LIST,
    "depends":        _T_DEPENDS,
    "endchoice":      _T_ENDCHOICE,
    "endif":          _T_ENDIF,
    "endmenu":        _T_ENDMENU,
    "env":            _T_ENV,
    "help":           _T_HELP,
    "hex":            _T_HEX,
    "if":             _T_IF,
    "imply":          _T_IMPLY,
    "int":            _T_INT,
    "mainmenu":       _T_MAINMENU,
    "menu":           _T_MENU,

    # 'menuconfig' only deals with presentation in the configuration interface
    # and doesn't affect evaluation semantics, so treat it the same as
    # 'config'. Perhaps some presentation-related support could be added as
    # well.
    "menuconfig":     _T_CONFIG,

    "modules":        _T_MODULES,
    "on":             _T_ON,
    "option":         _T_OPTION,
    "optional":       _T_OPTIONAL,
    "prompt":         _T_PROMPT,
    "range":          _T_RANGE,
    "select":         _T_SELECT,
    "source":         _T_SOURCE,
    "string":         _T_STRING,
    "tristate":       _T_TRISTATE,
    "visible":        _T_VISIBLE,
}.get

# Tokens after which identifier-like lexemes are treated as strings, plus
# _T_CONFIG. This allows us to quickly check if we have a symbol reference (as
# opposed to a definition or something else) when tokenizing.
_NOT_REF = frozenset((
    _T_BOOL,
    _T_CONFIG,
    _T_CHOICE,
    _T_COMMENT,
    _T_HEX,
    _T_INT,
    _T_MAINMENU,
    _T_MENU,
    _T_PROMPT,
    _T_SOURCE,
    _T_STRING,
    _T_TRISTATE,
))

# Note: This hack is no longer needed as of upstream commit c226456
# (kconfig: warn of unhandled characters in Kconfig commands). It
# is kept around for backwards compatibility.
#
# The initial word on a line is parsed specially. Let
# command_chars = [A-Za-z0-9_]. Then
#  - leading non-command_chars characters are ignored, and
#  - the first token consists the following one or more
#    command_chars characters.
# This is why things like "----help--" are accepted.
#
# In addition to the initial token, the regex also matches trailing whitespace
# so that we can jump straight to the next token (or to the end of the line if
# there's just a single token).
#
# As an optimization, this regex fails to match for lines containing just a
# comment.
_initial_token_re_match = re.compile(r"[^\w#]*(\w+)\s*").match

# Matches an identifier/keyword, also eating trailing whitespace
_id_keyword_re_match = re.compile(r"([\w./-]+)\s*").match

# Regular expression for finding $-references to symbols in strings
_sym_ref_re_search = re.compile(r"\$[A-Za-z0-9_]+").search

# Strings to use for types
_TYPENAME = {
    UNKNOWN: "unknown",
    BOOL: "bool",
    TRISTATE: "tristate",
    STRING: "string",
    HEX: "hex",
    INT: "int",
}

# Token to type mapping
_TOKEN_TO_TYPE = {
    _T_BOOL:         BOOL,
    _T_DEF_BOOL:     BOOL,
    _T_DEF_TRISTATE: TRISTATE,
    _T_HEX:          HEX,
    _T_INT:          INT,
    _T_STRING:       STRING,
    _T_TRISTATE:     TRISTATE,
}

# Default values for symbols of different types (the value the symbol gets if
# it is not assigned a user value and none of its 'default' clauses kick in)
_DEFAULT_VALUE = {
    BOOL:     "n",
    TRISTATE: "n",
    HEX:      "",
    INT:      "",
    STRING:   "",
}

# Indicates that no item is selected in a choice statement
_NO_SELECTION = 0

# Integers representing expression types
(
    _AND,
    _OR,
    _NOT,
    _EQUAL,
    _UNEQUAL,
    _LESS,
    _LESS_EQUAL,
    _GREATER,
    _GREATER_EQUAL,
) = range(9)

# Used in comparisons. 0 means the base is inferred from the format of the
# string. The entries for BOOL and TRISTATE are a convenience - they should
# never convert to valid numbers.
_TYPE_TO_BASE = {
    BOOL:     0,
    HEX:      16,
    INT:      10,
    STRING:   0,
    TRISTATE: 0,
    UNKNOWN:  0,
}

# Map from tristate values to integers
_TRI_TO_INT = {
    "n": 0,
    "m": 1,
    "y": 2,
}

_RELATIONS = frozenset((
    _EQUAL,
    _UNEQUAL,
    _LESS,
    _LESS_EQUAL,
    _GREATER,
    _GREATER_EQUAL,
))

# Token to relation (=, !=, <, ...) mapping
_TOKEN_TO_RELATION = {
    _T_EQUAL:         _EQUAL,
    _T_GREATER:       _GREATER,
    _T_GREATER_EQUAL: _GREATER_EQUAL,
    _T_LESS:          _LESS,
    _T_LESS_EQUAL:    _LESS_EQUAL,
    _T_UNEQUAL:       _UNEQUAL,
}

_RELATION_TO_STR = {
    _EQUAL:         "=",
    _GREATER:       ">",
    _GREATER_EQUAL: ">=",
    _LESS:          "<",
    _LESS_EQUAL:    "<=",
    _UNEQUAL:       "!=",
}
