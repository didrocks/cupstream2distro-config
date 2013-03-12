#!/usr/bin/env python

from distutils.core import setup
from setuptools import find_packages

setup(
    name='cupstream2distro-config',
    version='1.0',
    url='https://launchpad.net/cupstream2distro-config',
    packages=find_packages(),
    test_suite='tests',
    scripts=[
        'ci/cu2d-trigger',
        'ci/cu2d-update-ci',
        'daily-release/cu2d-update-stack'
    ],
)
