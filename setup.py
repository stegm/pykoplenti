from setuptools import setup

setup(
    name='kostalplenticore',
    version='1.0',
    py_modules=['kostal.plenticore'],
    install_requires=[
        "aiohttp==3.6.3",
        "pycryptodome==3.9.8",
        "prompt_toolkit==3.0.8",
        "click==7.1.2",
    ],
    entry_points='''
        [console_scripts]
        plenticore=kostal.plenticore.cli:cli
    ''',
)