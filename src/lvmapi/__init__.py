# encoding: utf-8

import os
import pathlib

from sdsstools import get_package_version
from sdsstools.configuration import get_config


# pip package name
NAME = "lvmapi"

# package name should be pip package name
__version__ = get_package_version(path=__file__, package_name=NAME)

internal_config_path = pathlib.Path(__file__).parent / "config.yaml"
config_path = os.getenv("LVMAPI_CONFIG_PATH", None)

config = get_config("lvmapi", config_file=internal_config_path, user_path=config_path)
