# -----------------------------------------------------------------------------
# Copyright (c) 2014--, The American Gut Development Team.
#
# Distributed under the terms of the BSD 3-clause License.
#
# The full license is in the file LICENSE, distributed with this software.
# -----------------------------------------------------------------------------

import json
from importlib.resources import files


with files('microsetta_interface').joinpath("server_config.json").open() as fp:
    SERVER_CONFIG = json.load(fp)
