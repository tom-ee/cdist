#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# 2016 Darko Poljak (darko.poljak at ungleich.ch)
#
# This file is part of cdist.
#
# cdist is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# cdist is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with cdist. If not, see <http://www.gnu.org/licenses/>.
#
#

import cdist
import cdist.config
import cdist.core
import cdist.preos
import argparse
import cdist.argparse
import logging
import os
import subprocess


class Debian(object):
    _preos_name = 'debian'
    _cdist_preos = True

    _files_dir = os.path.join(os.path.dirname(__file__), "files")

    @classmethod
    def default_args(cls):
        default_remote_exec = os.path.join(cls._files_dir, "remote-exec.sh")
        default_remote_copy = os.path.join(cls._files_dir, "remote-copy.sh")
        default_init_manifest = os.path.join(
            cls._files_dir, "init-manifest-{}".format(cls._preos_name))

        defargs = argparse.Namespace()
        defargs.arch = 'amd64'
        defargs.bootstrap = False
        defargs.configure = False
        defargs.cdist_params = '-v'
        defargs.rm_bootstrap_dir = False
        defargs.suite = 'stable'
        defargs.remote_exec = default_remote_exec
        defargs.remote_copy = default_remote_copy
        defargs.manifest = default_init_manifest

        return defargs

    @classmethod
    def get_parser(cls):
        defargs = cls.default_args()
        cdist_parser = cdist.argparse.get_parsers()
        parser = argparse.ArgumentParser(
                prog='cdist preos {}'.format(cls._preos_name),
                parents=[cdist_parser['loglevel'], cdist_parser['beta']])
        parser.add_argument('target_dir', nargs=1,
                            help=("target directory where PreOS will be "
                                  "bootstrapped"))
        parser.add_argument(
            '-a', '--arch',
            help="target debootstrap architecture, by default '{}'".format(
                defargs.arch), dest='arch', default=defargs.arch)
        parser.add_argument(
            '-B', '--bootstrap',
            help='do bootstrap step',
            dest='bootstrap', action='store_true', default=defargs.bootstrap)
        parser.add_argument(
            '-C', '--configure',
            help='do configure step',
            dest='configure', action='store_true', default=defargs.configure)
        parser.add_argument(
            '-c', '--cdist-params',
            help=("parameters that will be passed to cdist config, by default"
                  " '{}' is used".format(defargs.cdist_params)),
            dest='cdist_params', default=defargs.cdist_params)
        parser.add_argument(
            '-D', '--drive-boot',
            help='create bootable PreOS on specified drive',
            dest='drive')
        parser.add_argument(
            '-e', '--remote-exec',
            help=("remote exec that cdist config will use, by default "
                  "internal script is used"),
            dest='remote_exec', default=defargs.remote_exec)
        parser.add_argument(
            '-i', '--init-manifest',
            help=("init manifest that cdist config will use, by default "
                  "internal init manifest is used"),
            dest='manifest', default=defargs.manifest)
        parser.add_argument(
            '-k', '--keyfile', action="append",
            help=("ssh key files that will be added to cdist config; "
                  "'__ssh_authorized_keys root ...' type is appended to "
                  "initial manifest"),
            dest='keyfile')
        parser.add_argument(
            '-m', '--mirror',
            help='use specified mirror for debootstrap',
            dest='mirror')
        parser.add_argument('-p', '--pxe-boot-dir', help='PXE boot directory',
                            dest='pxe_boot_dir')
        parser.add_argument(
            '-r', '--rm-bootstrap-dir',
            help='remove target directory after finishing',
            dest='rm_bootstrap_dir', action='store_true',
            default=defargs.rm_bootstrap_dir)
        parser.add_argument(
            '-S', '--script',
            help='use specified script for debootstrap',
            dest='script')
        parser.add_argument('-s', '--suite',
                            help="suite used for debootstrap, "
                                 "by default '{}'".format(defargs.suite),
                            dest='suite', default=defargs.suite)
        parser.add_argument(
            '-t', '--trigger-command',
            help=("trigger command that will be added to cdist config; "
                  "'__cdist_preos_trigger http ...' type is appended to "
                  "initial manifest"),
            dest='trigger_command')
        parser.add_argument(
            '-y', '--remote-copy',
            help=("remote copy that cdist config will use, by default "
                  "internal script is used"),
            dest='remote_copy', default=defargs.remote_copy)
        parser.epilog = cdist.argparse.EPILOG

        return parser

    @classmethod
    def commandline(cls, argv):
        log = logging.getLogger(cls.__name__)

        parser = cls.get_parser()
        cdist.argparse.add_beta_command(cls._preos_name)
        args = parser.parse_args(argv)
        if args.script and not args.mirror:
            raise cdist.Error("script option cannot be used without "
                              "mirror option")

        args.command = cls._preos_name
        cdist.argparse.check_beta(vars(args))

        cdist.preos.check_root()

        args.target_dir = os.path.realpath(args.target_dir[0])
        args.os = cls._preos_name
        args.remote_exec = os.path.realpath(args.remote_exec)
        args.remote_copy = os.path.realpath(args.remote_copy)
        args.manifest = os.path.realpath(args.manifest)
        if args.keyfile:
            new_keyfile = [os.path.realpath(x) for x in args.keyfile]
            args.keyfile = new_keyfile
        if args.pxe_boot_dir:
            args.pxe_boot_dir = os.path.realpath(args.pxe_boot_dir)

        cdist.argparse.handle_loglevel(args)
        log.debug("preos: {}, args: {}".format(cls._preos_name, args))
        try:
            env = vars(args)
            new_env = {}
            for key in env:
                if key == 'verbose':
                    if env[key] >= 3:
                        new_env['debug'] = "yes"
                    elif env[key] == 2:
                        new_env['verbose'] = "yes"
                elif not env[key]:
                    new_env[key] = ''
                elif isinstance(env[key], bool) and env[key]:
                    new_env[key] = "yes"
                elif isinstance(env[key], list):
                    val = env[key]
                    new_env[key + "_cnt"] = str(len(val))
                    for i, v in enumerate(val):
                        new_env[key + "_" + str(i)] = v
                else:
                    new_env[key] = str(env[key])
            env = new_env
            env.update(os.environ)
            log.debug("preos: {} env: {}".format(cls._preos_name, env))
            cmd = os.path.join(cls._files_dir, "code")
            info_msg = ["Running preos: {}, suite: {}, arch: {}".format(
                cls._preos_name, args.suite, args.arch), ]
            if args.mirror:
                info_msg.append(", mirror: {}".format(args.mirror))
            if args.script:
                info_msg.append(", script: {}".format(args.script))
            if args.bootstrap:
                info_msg.append(", bootstrapping")
            if args.configure:
                info_msg.append(", configuring")
            if args.pxe_boot_dir:
                info_msg.append(", creating PXE")
            if args.drive:
                info_msg.append(", creating bootable drive")
            log.info(info_msg)
            log.debug("cmd={}".format(cmd))
            subprocess.check_call(cmd, env=env, shell=True)
        except subprocess.CalledProcessError as e:
            log.error("preos {} failed: {}".format(cls._preos_name, e))


class Ubuntu(Debian):
    _preos_name = "ubuntu"

    @classmethod
    def default_args(cls):
        defargs = super().default_args()
        defargs.suite = 'xenial'
        return defargs
