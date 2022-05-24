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
    name='acido',
    packages=['acido', 'acido.azure_utils', 'acido.utils'],
    version='0.12.1',
    description='Azure Container Instance Distributed Operations',
    long_description=readme,
    long_description_content_type='text/markdown',
    author='Xavier Álvarez',
    author_email='xalvarez@merabytes.com',
    url='https://github.com/merabytes/acido',
    license='MIT',
    install_requires=[
        'azure-cli==2.18.0',
        'azure-core==1.10.0',
        'azure-mgmt-core==1.2.1',
        'azure.identity==1.3',
        'azure.keyvault.secrets==4.2.0',
        'azure.storage.blob==12.7.1',
        'PyJWT==1.7.1',
        'websockets',
        'huepy',
        'msrestazure'
    ],
    keywords=[
        'Security',
        'Cloud Computing',
        'Red Team',
        'Pentesting'
    ],
    classifiers=[
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
    ]
)