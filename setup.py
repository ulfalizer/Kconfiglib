import io
import os
import setuptools

setuptools.setup(
    name="kconfiglib",
    # MAJOR.MINOR.PATCH, per http://semver.org
    version="10.19.1",
    description="A flexible Python Kconfig parser",

    # Make sure that README.rst decodes on Python 3 in environments that use
    # the C locale (which implies ASCII), by explicitly giving the encoding.
    #
    # io.open() has the 'encoding' parameter on both Python 2 and 3. open()
    # doesn't have it on Python 2. This lets us to use the same code for both.
    long_description=
        io.open(os.path.join(os.path.dirname(__file__), "README.rst"),
                encoding="utf-8").read(),

    url="https://github.com/ulfalizer/Kconfiglib",
    author='Ulf "Ulfalizer" Magnusson',
    author_email="ulfalizer@gmail.com",
    keywords="kconfig, kbuild, menuconfig",
    license="ISC",

    py_modules=(
        "kconfiglib",
        "menuconfig",
        "menuxconfig",
        "genconfig",
        "oldconfig",
        "olddefconfig",
        "alldefconfig",
        "allnoconfig",
        "allmodconfig",
        "allyesconfig",
    ),

    # TODO: Don't install the menuconfig on Python 2. It won't run there.
    # setuptools needs better documentation...
    entry_points={
        "console_scripts": (
            "menuconfig = menuconfig:_main",
            "menuxconfig = menuxconfig:main",
            "genconfig = genconfig:main",
            "oldconfig = oldconfig:_main",
            "olddefconfig = olddefconfig:main",
            "alldefconfig = alldefconfig:main",
            "allnoconfig = allnoconfig:main",
            "allmodconfig = allmodconfig:main",
            "allyesconfig = allyesconfig:main",
        )
    },

    # The terminal menuconfig implementation uses the standard Python 'curses'
    # module. The windows-curses package makes it available on Windows. See
    # https://github.com/zephyrproject-rtos/windows-curses.
    install_requires=(
        'windows-curses; sys_platform == "win32" and python_version >= "3"',
    ),

    # Needs support for unnumbered {} in format()
    python_requires=">=2.7,!=3.0.*",

    project_urls={
        "GitHub repository": "https://github.com/ulfalizer/Kconfiglib",
        "Examples": "https://github.com/ulfalizer/Kconfiglib/tree/master/examples",
    },

    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Build Tools",
        "Topic :: System :: Operating System Kernels :: Linux",
        "License :: OSI Approved :: ISC License (ISCL)",
        "Operating System :: POSIX",
        "Operating System :: Microsoft :: Windows",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.1",
        "Programming Language :: Python :: 3.2",
        "Programming Language :: Python :: 3.3",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
    ]
)
