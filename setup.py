#!/usr/bin/env python3

import sys
import os

from setuptools import setup

setup(
    name             = 'debocker',
    version          = '0.5',
    author           = 'Matthew Shaw',
    author_email     = 'mshaw.cx@gmail.com',
    license          = 'MIT',
    description      = 'Create Debian/Ubuntu Docker images',
    long_description = open('README.rst').read(),
    url              = 'https://github.com/shawcx/debocker',
    entry_points = {
        'console_scripts': [
            'debocker    = debocker:main',
            ]
        },
    py_modules = ['debocker'],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        ],
    zip_safe = True
    )
