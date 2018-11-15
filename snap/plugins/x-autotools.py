# -*- Mode:Python; indent-tabs-mode:nil; tab-width:4 -*-
#
# Copyright (C) 2015-2018 Canonical Ltd
# Copyright (C) 2016 Harald Sitter <sitter@kde.org>
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
import stat

from snapcraft.plugins import autotools


class XAutotoolsPlugin(autotools.AutotoolsPlugin):

    def env(self, root):
        env = super().env(root)
        if self.project.is_cross_compiling:
            env.extend([
                'CC={}-gcc'.format(self.project.arch_triplet),
                'CXX={}-g++'.format(self.project.arch_triplet),
            ])
        return env

    def build(self):
        env = os.environ.copy()
        stage_dir = self.project.stage_dir
        env['XDG_DATA_DIRS'] = ':'.join([
            os.path.join(stage_dir, 'usr/share'),
            '/usr/share'])
        env['PKG_CONFIG_PATH'] = os.path.join(stage_dir, 'pkgconfig-build')
        env['ACLOCAL_PATH'] = os.path.join(stage_dir, 'usr/share/aclocal')
        if self.name != 'vala':
            # The vala part is a special case, it boostraps itself using the
            # vala compiler on the host system and vapi files in the source
            # tree
            arch = self.project.arch_triplet
            env['GI_TYPELIB_PATH'] = ':'.join([
                os.path.join(stage_dir, 'usr/lib', arch, 'girepository-1.0'),
                os.path.join('/usr/lib', arch, 'girepository-1.0')])
            vapidirs = [
                os.path.join(stage_dir, 'usr/share/vala/vapi'),
                os.path.join(stage_dir, 'usr/share/vala-0.40/vapi'),
                os.path.join(stage_dir, 'usr/share/vala-0.36/vapi'),
                '/usr/share/vala-0.30/vapi']
            env['VAPIDIR'] = ':'.join(vapidirs)
            env['VALAFLAGS'] = ' '.join(['--vapidir ' + v for v in vapidirs])
            env['LD_LIBRARY_PATH'] = \
                os.path.join(stage_dir, 'usr/lib/vala-0.40')

        if not os.path.exists(os.path.join(self.builddir, 'configure')):
            generated = False
            scripts = ['autogen.sh', 'bootstrap']
            for script in scripts:
                path = os.path.join(self.builddir, script)
                if not os.path.exists(path) or os.path.isdir(path):
                    continue
                # Make sure it's executable
                if not os.access(path, os.X_OK):
                    os.chmod(path,
                             stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR |
                             stat.S_IRGRP | stat.S_IWGRP | stat.S_IXGRP |
                             stat.S_IROTH | stat.S_IWOTH | stat.S_IXOTH)
                self.run(
                    ['env', 'NOCONFIGURE=1', './{}'.format(script)], env=env)
                generated = True
                break
            if not generated:
                self.run(['autoreconf', '-i'], env=env)

        configure_command = ['./configure']

        if self.options.make_install_var:
            # Use an empty prefix since we'll install via DESTDIR
            configure_command.append('--prefix=')
        else:
            configure_command.append('--prefix=' + self.installdir)
        if self.project.is_cross_compiling:
            configure_command.append('--host={}'.format(self.project.deb_arch))
        self.run(configure_command + self.options.configflags, env=env)
        self.make(env=env)
