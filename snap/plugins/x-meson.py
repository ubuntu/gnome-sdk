# -*- Mode:Python; indent-tabs-mode:nil; tab-width:4 -*-
#
# Copyright (C) 2017-2018 Canonical Ltd
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os

from snapcraft.plugins import meson


class XMesonPlugin(meson.MesonPlugin):

    def _run_meson(self):
        os.makedirs(self.mesonbuilddir, exist_ok=True)
        meson_command = ['meson']
        if self.options.meson_parameters:
            meson_command.extend(self.options.meson_parameters)
        meson_command.append(self.snapbuildname)
        env = os.environ.copy()
        # Override pkg-config search path to use modified .pc files
        env['PKG_CONFIG_PATH'] = \
            os.path.join(self.project.stage_dir, 'pkgconfig-build')
        self.run(meson_command, env=env)
