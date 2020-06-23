# -----------------------------------------------------------------------------
# Copyright (c) 2014--, The American Gut Development Team.
#
# Distributed under the terms of the BSD 3-clause License.
#
# The full license is in the file LICENSE, distributed with this software.
# -----------------------------------------------------------------------------

import json
# NOTE: importlib replaces setuptools' pkg_resources as of Python 3.7
# See: https://stackoverflow.com/questions/6028000/how-to-read-a-static-file-from-inside-a-python-package # noqa
import importlib.resources as pkg_resources


with pkg_resources.open_text('microsetta_interface', "server_config.json") \
        as fp:
    SERVER_CONFIG = json.load(fp)
    SERVER_CONFIG['vioscreen_cryptokey'] = \
        SERVER_CONFIG['vioscreen_cryptokey'].encode('ascii')
