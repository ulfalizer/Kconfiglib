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

> $ python Kconfiglib/kconfigtest.py

You might want to use the "speedy" option. See kconfigtest.py.

The test suite failures for the following Blackfin defconfigs on e.g.
Linux 3.7.0-rc8 are due to
[a bug in the C implementation](https://lkml.org/lkml/2012/12/5/458):

arch/blackfin/configs/CM-BF537U\_defconfig  
arch/blackfin/configs/BF548-EZKIT\_defconfig  
arch/blackfin/configs/BF527-EZKIT\_defconfig  
arch/blackfin/configs/BF527-EZKIT-V2\_defconfig  
arch/blackfin/configs/TCM-BF537\_defconfig
