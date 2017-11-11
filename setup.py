import os
import setuptools

here_dir = os.path.dirname(__file__)
with open(os.path.join(here_dir, "README.rst")) as f:
    long_description = f.read()

setuptools.setup(
    name="kconfiglib",
    # MAJOR.MINOR.MAINTENANCE per http://semver.org
    version="2.0.2",
    description="A flexible Python Kconfig parser",
    long_description=long_description,
    url="https://github.com/ulfalizer/Kconfiglib",
    author='Ulf "Ulfalizer" Magnusson',
    author_email="ulfalizer@gmail.com",
    keywords="kconfig, kbuild",
    license="ISC",
    py_modules=["kconfiglib"],
    # This python_requires should be correct, but my setuptools is too old to
    # test it, so play it safe and leave it out for now. It's unlikely that
    # anyone's running ancient Python versions anyway, and the problem should
    # be obvious.
    #
    # 2.7+ for Python 2, 3.1+ for Python 3 (for unnumbered {} with format())
    # python_requires=">=2.7,!=3.0.*",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Build Tools",
        "Topic :: System :: Operating System Kernels :: Linux",
        "License :: OSI Approved :: ISC License (ISCL)",
        "Operating System :: POSIX",
        "Operating System :: Microsoft :: Windows",
        "Programming Language :: Python :: 2",
        # Needs support for unnumbered {} in format()
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        # Needs support for unnumbered {} in format()
        "Programming Language :: Python :: 3.1",
        "Programming Language :: Python :: 3.2",
        "Programming Language :: Python :: 3.3",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy"])
