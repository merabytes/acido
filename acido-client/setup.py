#!/usr/bin/env python

import os
import sys

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

with open('README.md', 'r', encoding='utf8', errors='ignore') as f:
    readme = f.read()

# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

setup(
    name='acido-client',
    packages=['acido_client'],
    version='0.40.2',
    description='REST API client for acido Lambda functions',
    long_description=readme,
    long_description_content_type='text/markdown',
    author='Xavier Álvarez',
    author_email='xalvarez@merabytes.com',
    url='https://github.com/merabytes/acido',
    license='MIT',
    install_requires=[
        'requests>=2.25.0',
    ],
    entry_points={
        'console_scripts': [
            'acido-client=acido_client.cli:main',
        ],
    },
    keywords=[
        'Security',
        'Cloud Computing',
        'Red Team',
        'Pentesting',
        'API Client'
    ],
    classifiers=[
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
    ]
)
