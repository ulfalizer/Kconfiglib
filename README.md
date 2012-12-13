Kconfiglib
==========

A Python library for doing stuff with Kconfig-based configuration systems. Can
extract information, query and set symbol values, and read and write .config
files. Highly compatible with the C implementation (the scripts/kconfig/\*conf
utilities in the kernel, usually invoked via make targets such as 'menuconfig'
and 'defconfig').

See kconfiglib.py for a longer introduction. The (extensive) documentation is
generated with

> $ pydoc [-w] kconfiglib

Installation instructions for the Linux kernel (in the kernel root):

> $ git clone git://github.com/ulfalizer/Kconfiglib.git
> $ git am Kconfiglib/makefile.patch

(Note: The directory name Kconfiglib/ is significant.)

Please tell me if the patch does not apply. It should be trivial to apply
manually.

The test suite is run with

> $ python Kconfiglib/testsuite.py

You might want to use the "speedy" option. See testsuite.py.

Please tell me if you miss some API instead of digging into internals. The
internal data structures and APIs, and dependency stuff in particular, are
unlikely to be exactly what you want as a user (hence why they're internal :).

Note: To make the API more consistent and intuitive, some methods have been
renamed as follows:
 * Symbol.calc\_value() -> Symbol.get\_value()
 * Choice.calc\_mode() -> Choice.get\_mode()
 * Symbol.set\_value() -> Symbol.set\_user\_value()
 * Choice.get\_actual\_items() -> Choice.get\_symbols()
 * Symbol.is\_choice\_item() -> Symbol.is\_choice\_symbol()
 * Symbol.reset() -> Symbol.unset\_user\_value()
 * Config.reset() -> Config.unset\_user\_values()


The test suite failures for the following Blackfin defconfigs on e.g.
Linux 3.7.0-rc8 are due to
[a bug in the C implementation](https://lkml.org/lkml/2012/12/5/458):

arch/blackfin/configs/CM-BF537U\_defconfig  
arch/blackfin/configs/BF548-EZKIT\_defconfig  
arch/blackfin/configs/BF527-EZKIT\_defconfig  
arch/blackfin/configs/BF527-EZKIT-V2\_defconfig  
arch/blackfin/configs/TCM-BF537\_defconfig
