# -*- Mode:Python; indent-tabs-mode:nil; tab-width:4 -*-
#
# Copyright (C) 2015-2018 Canonical Ltd
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

import snapcraft.plugins.cmake


class XCMakePlugin(snapcraft.plugins.cmake.CMakePlugin):

    def _build_environment(self):
        env = os.environ.copy()
        stage_dir = self.project.stage_dir
        arch = self.project.arch_triplet
        env['CMAKE_PREFIX_PATH'] = ':'.join(['$CMAKE_PREFIX_PATH', stage_dir])
        env['CMAKE_INCLUDE_PATH'] = ':'.join([
            '$CMAKE_INCLUDE_PATH',
            os.path.join(stage_dir, 'include'),
            os.path.join(stage_dir, 'usr/include'),
            os.path.join(stage_dir, 'include', arch),
            os.path.join(stage_dir, 'usr/include', arch)])
        env['CMAKE_LIBRARY_PATH'] = ':'.join([
            '$CMAKE_LIBRARY_PATH',
            os.path.join(stage_dir, 'lib'),
            os.path.join(stage_dir, 'usr/lib'),
            os.path.join(stage_dir, 'lib', arch),
            os.path.join(stage_dir, 'usr/lib', arch)])
        env['GI_TYPELIB_PATH'] = ':'.join([
            os.path.join(stage_dir, 'usr/lib', arch, 'girepository-1.0'),
            os.path.join('/usr/lib', arch, 'girepository-1.0')])
        env['VAPIDIR'] = ':'.join([
            os.path.join(stage_dir, 'usr/share/vala-0.36/vapi'),
            '/usr/share/vala-0.30/vapi'])
        env['XDG_DATA_DIRS'] = ':'.join([
            os.path.join(stage_dir, 'usr/share'),
            '/usr/share'])
        env['PKG_CONFIG_PATH'] = ':'.join([
            os.path.join(stage_dir, 'usr/lib/pkgconfig'),
            '/usr/lib/pkgconfig'])
        return env
