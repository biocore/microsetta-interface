# ----------------------------------------------------------------------------
# Copyright (c) 2019-, The Microsetta Initiative development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

from setuptools import setup, find_packages
from babel.messages import frontend as babel

import versioneer


command_classes = versioneer.get_cmdclass()
command_classes['compile_catalog'] = babel.compile_catalog


setup(
    name="microsetta-interface",
    author="Daniel McDonald",
    author_email="danielmcdonald@ucsd.edu",
    packages=find_packages(),
    version=versioneer.get_version(),
    cmdclass=command_classes,
    url="https://github.com/biocore/microsetta-interface",
    description="The Microsetta participant interface",
    license='BSD-3-Clause',
    package_data={
        '': ['translations/*/*/*.mo',
             'translations/*/*/*.po'],
        'microsetta_interface': [
            'routes.yaml',
            'server_config.json',
            'templates/*.*',
            'static/*',
            'static/css/*',
            'static/img/*',
            'static/js/*',
            'static/vendor/js/*',
            'static/vendor/images/*',
            'static/vendor/css/*',
            'static/vendor/js/jquery.form-4.2.2/*',
            'static/vendor/jquery-ui-1.12.1/*',
            'static/vendor/jquery-ui-1.12.1/images/*',
            'static/vendor/popper-1.11.0/*',
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
            'static/vendor/DataTables/*',
            'static/vendor/DataTables/Buttons-1.6.2/js/*',
            'static/vendor/DataTables/Buttons-1.6.2/css/*',
            'static/vendor/DataTables/PercentageBars-1.10.21/js/*',
            'static/vendor/DataTables/PercentageBars-1.10.21/css/*',
            'static/vendor/emperor/*',
            'static/vendor/emperor/css/*',
            'static/vendor/emperor/img/*',
            'static/vendor/emperor/js/*',
            'static/vendor/emperor/templates/*',
            'static/vendor/emperor/vendor/*',
            'static/vendor/emperor/vendor/css/*',
            'static/vendor/emperor/vendor/css/font/*',
            'static/vendor/emperor/vendor/css/images/*',
            'static/vendor/emperor/vendor/js/*',
            'static/vendor/emperor/vendor/js/three.js-plugins/*',
            'static/vendor/emperor/vendor/',
            'authrocket.pubkey']},
)
