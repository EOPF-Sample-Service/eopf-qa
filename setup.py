from __future__ import print_function
from setuptools import setup, find_packages
from setuptools.command.test import test as TestCommand
import io
import codecs
import os
import sys

here = os.path.abspath(os.path.dirname(__file__))

def read(*filenames, **kwargs):
    encoding = kwargs.get('encoding', 'utf-8')
    sep = kwargs.get('sep', '\n')
    buf = []
    for filename in filenames:
        with io.open(filename, encoding=encoding) as f:
            buf.append(f.read())
    return sep.join(buf)

long_description = read('README.txt', 'CHANGES.txt')

class PyTest(TestCommand):
    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        import pytest
        errcode = pytest.main(self.test_args)
        sys.exit(errcode)

setup(
    name='eopf_qa',
    version=eopf_qa.__version__,
    url='https://github.com/EOPF-Sample-Service/eopf-qa',
    license='Apache Software License',
    author='Christoph Reck',
    tests_require=['pytest'],
    install_requires=['Flask>=0.10.1',
                    'Flask-SQLAlchemy>=1.0',
                    ],
    cmdclass={'test': PyTest},
    author_email='nospam4reck@gmx.org',
    description='EOPF Zarr Product quality checks',
    long_description=long_description,
    packages=['eopf_qa'],
    include_package_data=True,
    platforms='any',
    test_suite='eopf_qa.test.test_eopf_qa',
    classifiers = [
        'Programming Language :: Python',
        'Development Status :: 3 - Alfa',
        'Natural Language :: English',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: File Formats :: EOPF :: Quality Assurance',
        'Topic :: Database :: Servers :: STAC'
        'Topic :: Scientific/Engineering :: GIS',
        ],
    extras_require={
        'testing': ['pytest'],
    }
)