# -*- coding: utf-8 -*-

from os.path import dirname

from setuptools import setup
from setuptools.command.build_py import build_py
from setuptools.command.install import install

VERSION = '0.0.2'


def build_qt_resources():
    print('Compiling resources...')
    try:
        from PyQt5 import pyrcc_main
    except ImportError as e:
        raise Exception("Building from source requires PyQt5") from e
    pyrcc_main.processResourceFile(['vqttt/resources/resources.qrc'],
                                   'vqttt/resources.py', False)
    # Rewrite PyQt5 import statements to qtpy
    with open('vqttt/resources.py', 'r') as rf:
        lines = rf.readlines()
        for i, line in enumerate(lines):
            if 'import' in line and not line.startswith('\\x'):
                new_line = line.replace('PyQt5', 'qtpy')
                lines[i] = new_line
    with open('vqttt/resources.py', 'w') as wf:
        wf.writelines(lines)
    print('Resources compiled successfully')


class CustomInstall(install):
    def run(self):
        try:
            build_qt_resources()
        except Exception as e:
            print('Could not compile the resources.py file due to an exception: "{}"\n'
                  'Aborting build.'.format(e))
            raise
        install.run(self)


class CustomBuild(build_py):
    def run(self):
        try:
            build_qt_resources()
        except Exception as e:
            print('Could not compile the resources.py file due to an exception: "{}"\n'
                  'Aborting build.'.format(e))
            raise
        build_py.run(self)


setup(
    name="vqttt",
    version=VERSION,
    description="Vakio MQTT GUI Client",
    packages=["vqttt"],

    author="bus1111",
    author_email="vodnik.sila@mail.ru",
    url="https://github.com/bus1111/vqttt/",

    python_requires=">=3.5",
    install_requires=['PyQt5;platform_system=="Darwin"',   # it's better to use distro-supplied
                      'PyQt5;platform_system=="Windows"',  # PyQt package on Linux
                      'QtPy', 'paho-mqtt'],

    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: X11 Applications :: Qt",
        "Environment :: MacOS X :: Cocoa",
        "Environment :: Win32 (MS Windows)",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3 :: Only",
    ],
    download_url="https://github.com/bus1111/vqttt/archive/{}.zip".format(VERSION),
    entry_points={'console_scripts': 'vqttt=vqttt:main'},
    include_package_data=True,
    keywords=["mqtt", "gui", "qt"],
    zip_safe=False,
    cmdclass=dict(install=CustomInstall, build_py=CustomBuild)
)
