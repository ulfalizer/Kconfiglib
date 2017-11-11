.. contents:: Table of contents
   :backlinks: none

Overview
--------

*This is version 2 of Kconfiglib, which is not backwards-compatible with
Kconfiglib 1. For a summary of changes between Kconfiglib 1 and Kconfiglib 2,
see* |changes|_.

.. _changes: kconfiglib-2-changes.txt
.. |changes| replace:: *kconfiglib-2-changes.txt*

Kconfiglib is a Python 2/3 library for scripting and extracting information
from `Kconfig
<https://www.kernel.org/doc/Documentation/kbuild/kconfig-language.txt>`_
configuration systems. It can do the following, among other things:

- **Programmatically get and set symbol values**

  `allnoconfig.py <examples/allnoconfig.py>`_ and `allyesconfig.py
  <examples/allyesconfig.py>`_ examples are provided, automatically verified to
  produce identical output to the standard ``make allnoconfig`` and ``make
  allyesconfig``.

- **Read and write .config files**

  The generated ``.config`` files are character-for-character identical to what
  the C implementation would generate (except for the header comment). The test
  suite relies on this, as it compares the generated files.

- **Inspect symbols**

  Printing a symbol gives output which could be fed back into a Kconfig parser
  to redefine it***. The printing function (``__str__()``) is implemented with
  public APIs, meaning you can fetch just whatever information you need as
  well.

  A helpful ``__repr__()`` is implemented on all objects too, also implemented
  with public APIs.

  \***Choice symbols get their parent choice as a dependency, which shows up as
  e.g. ``prompt "choice symbol" if <choice>`` when printing the symbol. This
  could easily be worked around if 100% reparsable output is needed.

- **Inspect expressions**

  Expressions use a simple tuple-based format that can be processed manually
  if needed. Expression printing and evaluation functions are provided,
  implemented with public APIs.

- **Inspect the menu tree**

  The underlying menu tree is exposed, including submenus created implicitly
  from symbols depending on preceding symbols. This can be used e.g. to
  implement menuconfig-like functionality.
  
  See the `menuconfig.py <examples/menuconfig.py>`_ example.


Here are some other features:

- **Single-file implementation**
  
  The entire library is contained in `kconfiglib.py <kconfiglib.py>`_.

- **Runs unmodified under both Python 2 and Python 3**
  
  The code mostly uses basic Python features and has no third-party
  dependencies. The most advanced things used are probably ``@property`` and
  ``__slots__``.

- **Robust and highly compatible with the standard Kconfig C tools**
  
  The test suite automatically compares output from Kconfiglib and the C tools
  by diffing the generated ``.config`` files for the real kernel Kconfig and
  defconfig files, for all ARCHes.
  
  This currently involves comparing the output for 36 ARCHes and 498 defconfig
  files (or over 18000 ARCH/defconfig combinations in "obsessive" test suite
  mode). All tests are expected to pass.

  A comprehensive suite of selftests is included as well.

- **Not horribly slow despite being a pure Python implementation**
  
  The `allyesconfig.py <examples/allyesconfig.py>`_ example currently runs in
  about 1.6 seconds on a Core i7 2600K (with a warm file cache), where half a
  second is overhead from ``make scriptconfig``.

  For long-running jobs, `PyPy <https://pypy.org/>`_ gives a big performance
  boost. CPython is faster for short-running jobs as PyPy needs some time to
  warm up.

- **Internals that (mostly) mirror the C implementation**
  
  While being simpler to understand.
  
Documentation
-------------

Kconfiglib comes with extensive documentation in the form of docstrings. To view it, run e.g.
the following command:

.. code:: sh

    $ pydoc kconfiglib
    
For HTML output, add ``-w``:

.. code:: sh

    $ pydoc -w kconfiglib
    
A good starting point is to read the module docstring (which you could also just read directly
at the beginning of `kconfiglib.py <kconfiglib.py>`_). It gives an introduction to symbol
values, the menu tree, and expressions.

After reading the module docstring, a good next step is to read the ``Kconfig`` class
documentation, and then the documentation for the ``Symbol``, ``Choice``, and ``MenuNode``
classes.

Please tell me if something is unclear to you or can be explained better.

Installation
------------

Installation with pip
~~~~~~~~~~~~~~~~~~~~~

Kconfiglib is available on `PyPI <https://pypi.python.org/pypi/kconfiglib/>`_ and can be
installed with e.g.

.. code::

    $ pip(3) install kconfiglib --user

All releases have a corresponding tag in the git repository, e.g. ``v2.0.2``.
`Semantic versioning <http://semver.org/>`_ is used.

Installation for the Linux kernel
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

See the module docstring at the top of `kconfiglib.py <kconfiglib.py>`_.

Manual installation
~~~~~~~~~~~~~~~~~~~

The entire library is contained in
`kconfiglib.py <https://github.com/ulfalizer/Kconfiglib/blob/master/kconfiglib.py>`_.
Just drop it somewhere.

Examples
--------

Example scripts
~~~~~~~~~~~~~~~

The `examples/ <examples/>`_ directory contains some simple example scripts. Among these are the following ones:

- `allnoconfig.py <examples/allnoconfig.py>`_, `allnoconfig_simpler.py <examples/allnoconfig_simpler.py>`_, and `allyesconfig.py <examples/allyesconfig.py>`_ implement ``make allnoconfig`` and ``make allyesconfig`` in various ways. Demonstrates menu tree walking and value setting.

- `defconfig.py <examples/defconfig.py>`_ has the same effect as going into ``make menuconfig`` and immediately saving and exiting.

- `eval_expr.py <examples/eval_expr.py>`_ evaluates an expression in the context of a configuration.

- `find_symbol.py <examples/find_symbol.py>`_ searches through expressions to find references to a symbol, also printing a "backtrace" with parents for each reference found.

- `help_grep.py <examples/help_grep.py>`_ searches for a string in all help texts.

- `print_tree.py <examples/print_tree.py>`_ prints a tree of all configuration items.

- `menuconfig.py <examples/menuconfig.py>`_ implements a configuration interface that uses notation similar to ``make menuconfig``. It's deliberately kept as simple as possible to demonstrate just the core concepts, and isn't something you'd actually want to use. Here's a screenshot:

.. code-block::

    ======== Example Kconfig configuration ========

    [*] Enable loadable module support (MODULES)
        Bool and tristate symbols
            [*] Bool symbol (BOOL)
                    [ ] Dependent bool symbol (BOOL_DEP)
                    < > Dependent tristate symbol (TRI_DEP)
                    [ ] First prompt (TWO_MENU_NODES)
            < > Tristate symbol (TRI)
            [ ] Second prompt (TWO_MENU_NODES)
                *** These are selected by TRI_DEP ***
            < > Tristate selected by TRI_DEP (SELECTED_BY_TRI_DEP)
            < > Tristate implied by TRI_DEP (IMPLIED_BY_TRI_DEP)
        String, int, and hex symbols
            (foo) String symbol (STRING)
            (747) Int symbol (INT)
            (0xABC) Hex symbol (HEX)
        Various choices
            -*- Bool choice (BOOL_CHOICE)
                    --> Bool choice sym 1 (BOOL_CHOICE_SYM_1)
                        Bool choice sym 2 (BOOL_CHOICE_SYM_2)
            {M} Tristate choice (TRI_CHOICE)
                    < > Tristate choice sym 1 (TRI_CHOICE_SYM_1)
                    < > Tristate choice sym 2 (TRI_CHOICE_SYM_2)
            [ ] Optional bool choice (OPT_BOOL_CHOICE)

    Enter a symbol/choice name, "load_config", or "write_config" (or press CTRL+D to exit): BOOL
    Value for BOOL (available: n, y): n
    ...
    
I'm not currently interested in implementing a (more usable) menuconfig myself, but all the infrastructure
for a great one should be there if you want to give it a go. I'll help you out with any questions you might
have.

Real-world examples
~~~~~~~~~~~~~~~~~~~

These use the older Kconfiglib 1 API, which was clunkier and not as general (functions instead of properties, no direct access to the menu structure or properties, uglier ``__str__()`` output):

- `genboardscfg.py <http://git.denx.de/?p=u-boot.git;a=blob;f=tools/genboardscfg.py;hb=HEAD>`_ from `Das U-Boot <http://www.denx.de/wiki/U-Boot>`_ generates some sort of legacy board database by pulling information from a newly added Kconfig-based configuration system (as far as I understand it :).

- `gen-manual-lists.py <https://git.busybox.net/buildroot/tree/support/scripts/gen-manual-lists.py?id=5676a2deea896f38123b99781da0a612865adeb0>`_ generated listings for an appendix in the `Buildroot <https://buildroot.org>`_ manual. (The listing has since been removed.)

- `gen_kconfig_doc.py <https://github.com/espressif/esp-idf/blob/master/docs/gen-kconfig-doc.py>`_ from the `esp-idf <https://github.com/espressif/esp-idf>`_ project generates documentation from Kconfig files.

- `SConf <https://github.com/CoryXie/SConf>`_ builds an interactive configuration interface (like ``menuconfig``) on top of Kconfiglib, for use e.g. with `SCons <scons.org>`_.

- `kconfig-diff.py <https://gist.github.com/dubiousjim/5638961>`_ -- a script by `dubiousjim <https://github.com/dubiousjim>`_ that compares kernel configurations.

- Originally, Kconfiglib was used in chapter 4 of my `master's thesis <http://liu.diva-portal.org/smash/get/diva2:473038/FULLTEXT01.pdf>`_ to automatically generate a "minimal" kernel for a given system. Parts of it bother me a bit now, but that's how it goes with old work.

Sample ``make iscriptconfig`` session
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The following log should give some idea of the functionality available in the API:

.. code-block::

    $ make iscriptconfig
    A Kconfig instance 'kconf' for the architecture x86 has been created.
    >>> kconf  # Calls Kconfig.__repr__()
    <configuration with 13711 symbols, main menu prompt "Linux/x86 4.14.0-rc7 Kernel Configuration", srctree ".", config symbol prefix "CONFIG_", warnings enabled, undef. symbol assignment warnings disabled>
    >>> kconf.mainmenu_text  # Expanded main menu text
    'Linux/x86 4.14.0-rc7 Kernel Configuration'
    >>> kconf.top_node  # The implicit top-level menu
    <menu node for menu, prompt "Linux/$ARCH $KERNELVERSION Kernel Configuration" (visibility y), deps y, 'visible if' deps y, has child, Kconfig:5>
    >>> kconf.top_node.list  # First child menu node
    <menu node for symbol SRCARCH, deps y, has next, Kconfig:7>
    >>> print(kconf.top_node.list)  # Calls MenuNode.__str__()
    config SRCARCH
    	string
    	option env="SRCARCH"
    	default "x86"
    
    >>> sym = kconf.top_node.list.next.item  # Item contained in next menu node
    >>> print(sym)  # Calls Symbol.__str__()
    config 64BIT
    	bool
    	prompt "64-bit kernel" if ARCH = "x86"
    	default ARCH != "i386"
    	help
    	  Say yes to build a 64-bit kernel - formerly known as x86_64
    	  Say no to build a 32-bit kernel - formerly known as i386
    
    >>> sym  # Calls Symbol.__repr__()
    <symbol 64BIT, bool, "64-bit kernel", value y, visibility y, direct deps y, arch/x86/Kconfig:2>
    >>> sym.assignable  # Currently assignable values (0, 1, 2 = n, m, y)
    (0, 2)
    >>> sym.set_value(0)  # Set it to n
    True
    >>> sym.tri_value  # Check the new value
    0
    >>> sym = kconf.syms["X86_MPPARSE"]  # Look up symbol by name
    >>> print(sym)
    config X86_MPPARSE
    	bool
    	prompt "Enable MPS table" if (ACPI || SFI) && X86_LOCAL_APIC
    	default "y" if X86_LOCAL_APIC
    	help
    	  For old smp systems that do not have proper acpi support. Newer systems
    	  (esp with 64bit cpus) with acpi support, MADT and DSDT will override it
    
    >>> default = sym.defaults[0]  # Fetch its first default
    >>> sym = default[1]  # Fetch the default's condition (just a Symbol here)
    >>> print(sym)  # Print it. Dependencies are propagated to properties, like in the C implementation.
    config X86_LOCAL_APIC
    	bool
    	default "y" if X86_64 || SMP || X86_32_NON_STANDARD || X86_UP_APIC || PCI_MSI
    	select IRQ_DOMAIN_HIERARCHY if X86_64 || SMP || X86_32_NON_STANDARD || X86_UP_APIC || PCI_MSI
    	select PCI_MSI_IRQ_DOMAIN if PCI_MSI && (X86_64 || SMP || X86_32_NON_STANDARD || X86_UP_APIC || PCI_MSI)
    
    >>> sym.nodes  # Show the MenuNode(s) associated with it
    [<menu node for symbol X86_LOCAL_APIC, deps n, has next, arch/x86/Kconfig:1015>]
    >>> kconfiglib.expr_str(sym.defaults[0][1])  # Print the default's condition
    'X86_64 || SMP || X86_32_NON_STANDARD || X86_UP_APIC || PCI_MSI'
    >>> kconfiglib.expr_value(sym.defaults[0][1])  # Evaluate it (0 = n)
    0
    >>> kconf.syms["64BIT"].set_value(2)
    True
    >>> kconfiglib.expr_value(sym.defaults[0][1])  # Evaluate it again (2 = y)
    2
    >>> kconf.write_config("myconfig")  # Save a .config
    >>> ^D
    $ cat myconfig
    # Generated by Kconfiglib (https://github.com/ulfalizer/Kconfiglib)
    CONFIG_64BIT=y
    CONFIG_X86_64=y
    CONFIG_X86=y
    CONFIG_INSTRUCTION_DECODER=y
    CONFIG_OUTPUT_FORMAT="elf64-x86-64"
    CONFIG_ARCH_DEFCONFIG="arch/x86/configs/x86_64_defconfig"
    CONFIG_LOCKDEP_SUPPORT=y
    CONFIG_STACKTRACE_SUPPORT=y
    CONFIG_MMU=y
    ...
 
Test suite
----------

The test suite is run with

.. code::

    $ python(3) Kconfiglib/testsuite.py
    
`pypy <http://pypy.org>`_ works too, and is much speedier for everything except ``allnoconfig.py``/``allnoconfig_simpler.py``/``allyesconfig.py``, where it doesn't have time to warm up since
the scripts are run via ``make scriptconfig``.

The test suite must be run from the top-level kernel directory. It requires that the
Kconfiglib git repository has been cloned into it and that the makefile patch has been applied.

**NOTE: The test suite overwrites .config in the kernel root, so make sure to back it up.**

The test suite consists of a set of selftests and a set of compatibility tests that
compare configurations generated by Kconfiglib with
configurations generated by the C tools, for a number of cases. See
`testsuite.py <https://github.com/ulfalizer/Kconfiglib/blob/master/testsuite.py>`_
for the available options. You might want to use the "speedy" option to speed things
up a bit.

The test suite might fail for a few configurations for kernels older than April 2016,
when a fix was added to Kconfig that's also mirrored in Kconfiglib
(see `this commit <https://github.com/ulfalizer/Kconfiglib/commit/35ea8d5f1d63bdc9f8642f5ce4445e8f7c914385>`_).
This is harmless, and only counts as a fail since the test suite compares literal
output from the kconfig version that's bundled with the kernel.

A lot of time is spent waiting around for ``make`` and the C utilities (which need to reparse all the
Kconfig files for each defconfig test). Adding some multiprocessing to the test suite would make sense
too.

Notes
-----

* Kconfiglib assumes the modules symbol is ``MODULES``, which is backwards-compatible.
  A warning is printed by default if ``option modules`` is set on some other symbol.
  
  Let me know if you need proper ``option modules`` support. It wouldn't be that
  hard to add.

* `fpemud <https://github.com/fpemud>`_ has put together
  `Python bindings <https://github.com/fpemud/pylkc>`_ to internal functions in the C
  implementation. This is an alternative to Kconfiglib's all-Python approach.

* The test suite failures (should be the only ones) for the following Blackfin
  defconfigs on e.g. Linux 3.7.0-rc8 are due to
  `a bug in the C implementation <https://lkml.org/lkml/2012/12/5/458>`_:

  * ``arch/blackfin/configs/CM-BF537U_defconfig``
  * ``arch/blackfin/configs/BF548-EZKIT_defconfig``
  * ``arch/blackfin/configs/BF527-EZKIT_defconfig``
  * ``arch/blackfin/configs/BF527-EZKIT-V2_defconfig``
  * ``arch/blackfin/configs/TCM-BF537_defconfig``

Thanks
------

Thanks to `Philip Craig <https://github.com/philipc>`_ for adding
support for the ``allnoconfig_y`` option and fixing an obscure issue
with ``comment``\s inside ``choice``\s (that didn't affect correctness but
made outputs differ). ``allnoconfig_y`` is used to force certain symbols
to ``y`` during ``make allnoconfig`` to improve coverage.
