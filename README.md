Kconfiglib
==========

A parser for the Linux kernel's configuration language, Kconfig. Presents
configuration symbols as objects that can be queried and assigned values,
automatically invalidating and reevaluating dependent symbols as needed.
Supports reading and writing .config files. Highly compatible with the C
implementation. See kconfiglib.py for a longer introduction.

I mainly wrote this for my master's thesis
(http://liu.diva-portal.org/smash/get/diva2:473038/FULLTEXT01), to
automatically generate a minimal kernel configuration for a given system. See
Chapter 4 - Boot time optimization through semi-automatic kernel minimization.

Haven't worked on this in a long time. Not sure if it will work with recent
Kconfig versions.
