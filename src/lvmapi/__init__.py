# encoding: utf-8

from sdsstools import get_package_version


# pip package name
NAME = "lvmapi"

# package name should be pip package name
__version__ = get_package_version(path=__file__, package_name=NAME)
