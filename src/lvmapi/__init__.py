# encoding: utf-8

import pathlib

from sdsstools import get_package_version, read_yaml_file


# pip package name
NAME = "lvmapi"

# package name should be pip package name
__version__ = get_package_version(path=__file__, package_name=NAME)


config = read_yaml_file(pathlib.Path(__file__).parent / "config.yaml")
