.. contents:: Table of contents
   :backlinks: none

Overview
--------

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
  second is overhead from ``make scriptconfig`` (see below).

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

All releases have a corresponding tag in the git repository, e.g. ``v1.0.6``.
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

* The `examples/ <https://github.com/ulfalizer/Kconfiglib/tree/master/examples>`_ directory contains simple example scripts. See the documentation for how to run them.

* `genboardscfg.py <http://git.denx.de/?p=u-boot.git;a=blob;f=tools/genboardscfg.py;hb=HEAD>`_ from `Das U-Boot <http://www.denx.de/wiki/U-Boot>`_ generates some sort of legacy board database by pulling information from a newly added Kconfig-based configuration system (as far as I understand it :).

* `gen-manual-lists.py <https://git.busybox.net/buildroot/tree/support/scripts/gen-manual-lists.py?id=5676a2deea896f38123b99781da0a612865adeb0>`_ generated listings for an appendix in the `Buildroot <https://buildroot.org>`_ manual. (The listing has since been removed.)

* `SConf <https://github.com/CoryXie/SConf>`_ builds an interactive configuration interface (like ``menuconfig``) on top of Kconfiglib, for use e.g. with `SCons <scons.org>`_.

* `kconfig-diff.py <https://gist.github.com/dubiousjim/5638961>`_ -- a script by `dubiousjim <https://github.com/dubiousjim>`_ that compares kernel configurations.

* Originally, Kconfiglib was used in chapter 4 of my `master's thesis <http://liu.diva-portal.org/smash/get/diva2:473038/FULLTEXT01.pdf>`_ to automatically generate a "minimal" kernel for a given system. Parts of it bother me a bit now, but that's how it goes with old work.
 
Test suite
----------

The test suite is run with

.. code::

    $ python(3) Kconfiglib/testsuite.py
    
(`pypy <http://pypy.org>`_ works too, and is much speedier.)

The test suite must be run from the top-level kernel directory. It requires that the git
repository has been cloned into it and that ``makefile.patch`` has been applied.

**NOTE: Some tests currently overwrite .config in the kernel root, so make sure to back it up.**

The test suite consists of a set of selftests and a set of compatibility tests that
compare (character for character) configurations generated by Kconfiglib with
configurations generated by ``scripts/kconfig/conf`` for a number of cases. You
might want to use the "speedy" option; see
`testsuite.py <https://github.com/ulfalizer/Kconfiglib/blob/master/testsuite.py>`_.

The test suite might fail for a few configurations for kernels older than April 2016,
when a fix was added to Kconfig that's also mirrored in Kconfiglib
(see `this commit <https://github.com/ulfalizer/Kconfiglib/commit/35ea8d5f1d63bdc9f8642f5ce4445e8f7c914385>`_).
This is harmless, and only counts as a fail since the test suite compares literal
output from the kconfig version that's bundled with the kernel.

Kconfiglib is much faster than the test suite would indicate. Most of the time
is spent waiting around for ``make`` or the C utilities. Adding some multiprocessing
to the test suite would make sense.

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
