#!/usr/bin/env python

"""Setup script for the kconfiglib module."""

from distutils.core import setup

setup (# Distribution meta-data
       name = "kconfiglib",
       version = "0.0.1",
       description = "A flexible Python Kconfig parser",
       author = "Ulf Magnusson",
       author_email = "ulfalizer@gmail.com",
       url = "https://github.com/ulfalizer/Kconfiglib",

       # Description of the modules and packages in the distribution
       py_modules = ['kconfiglib'],
      )
