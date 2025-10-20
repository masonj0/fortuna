# setup.py
from setuptools import setup, find_packages

with open('requirements.txt') as f:
    requirements = f.read().splitlines()

setup(
    name='fortuna_engine',
    version='1.0.0',
    packages=find_packages(),
    author='Jules',
    author_email='',
    description='The Python backend for the Fortuna Faucet application.',
    long_description='This package contains the FastAPI server and all related data adapters and analysis tools.',
    install_requires=requirements,
    entry_points={
        'console_scripts': [
            'fortuna-engine=python_service.run_api:main',
        ],
    },
    include_package_data=True,
    package_data={
        'python_service': ['*.py'],
    },
)
