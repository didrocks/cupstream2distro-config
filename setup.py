#!/usr/bin/env python

from distutils.core import setup
from setuptools import find_packages
import os


def get_files(directory):
    return [os.path.join(directory, f) for f in os.listdir(directory)]

def get_data_files():
    result = [
        ('/usr/share/cupstream2distro-config/ci/config',
         get_files('ci/config')),
        ('/usr/share/cupstream2distro-config/ci/jenkins-templates',
         get_files('ci/jenkins-templates')),
        ('/usr/share/cupstream2distro-config/daily-release/config',
         get_files('daily-release/config')),
        ('/usr/share/cupstream2distro-config/daily-release/jenkins-templates',
         get_files('daily-release/jenkins-templates/')),
    ]
    config_path = '/etc/cupstream2distro-config/stacks'
    for dir in os.listdir('stacks'):
        stack_dir = os.path.join('stacks', dir)
        result.append((
            os.path.join(config_path, stack_dir),
            os.listdir(stack_dir)
        ))
    return result

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
    data_files=get_data_files(),
)
