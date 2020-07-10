# ----------------------------------------------------------------------------
# Copyright (c) 2019-, The Microsetta Initiative development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

from setuptools import setup, find_packages

import versioneer

setup(
    name="microsetta-interface",
    author="Daniel McDonald",
    author_email="danielmcdonald@ucsd.edu",
    packages=find_packages(),
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    url="https://github.com/biocore/microsetta-interface",
    description="The Microsetta participant interface",
    license='BSD-3-Clause',
    package_data={'microsetta_interface': [
        'routes.yaml',
        'server_config.json',
        'templates/*.*',
        'static/*',
        'static/css/*',
        'static/img/*',
        'static/vendor/js/*',
        'static/vendor/css/*',
        'static/vendor/js/jquery.form-4.2.2/*',
        'static/vendor/jquery-ui-1.12.1/*',
        'static/vendor/jquery-ui-1.12.1/images/*',
        'static/vendor/bootstrap-4.4.1-dist/js/*',
        'static/vendor/bootstrap-4.4.1-dist/css/*',
        'static/vendor/bootstrap-datetimepicker-4.14.30/*',
        'static/vendor/vue-form-generator-2.3.4/*',
        'static/vendor/bootstrap-3.3.7-dist/js/*',
        'static/vendor/bootstrap-3.3.7-dist/css/*',
        'static/vendor/bootstrap-3.3.7-dist/fonts/*',
        'static/vendor/bootstrap-3.3.7-dist/fonts/*',
        'static/vendor/font-awesome-4.7.0/css/*',
        'static/vendor/font-awesome-4.7.0/less/*',
        'static/vendor/font-awesome-4.7.0/fonts/*',
        'static/vendor/font-awesome-4.7.0/scss/*',
        'authrocket.pubkey']},
)
