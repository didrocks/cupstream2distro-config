""" Validate stack config for obvious errors

- Reads stack configuration from YAML configuration files
- performs validation checks

"""
# Copyright (C) 2013, Canonical Ltd (http://www.canonical.com/)
#
# Author: Martin Mrazik <martin.mrazik@canonical.com>
#
# This software is free software: you can redistribute it
# and/or modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation, either version 3 of
# the License, or (at your option) any later version.
#
# This software is distributed in the hope that it will
# be useful, but WITHOUT ANY WARRANTY; without even the implied warranty
# of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this software.  If not, see <http://www.gnu.org/licenses/>.

import argparse
import logging
import copy
import os
import fnmatch
from copy import deepcopy

from c2dconfigutils import (
    dict_union, load_default_cfg, load_stack_cfg, set_logging)


class StacksValidator(object):
    DEFAULT_STACKS_CFG_PATH = '../stacks/'

    def parse_arguments(self):
        """ Parses the command line arguments

        return args: the parsed arguments
        """
        parser = argparse.ArgumentParser(
            description='''Validate stacks for obvious errors''')
        parser.add_argument('-d', '--debug', action='store_true',
                            default=False, help='enable debug mode')
        parser.add_argument('-D', '--stackcfg-dir',
                            default=self.DEFAULT_STACKS_CFG_PATH,
                            help='Path to directory with stacks definition. ' +
                            '(default: {}).'.format(
                                self.DEFAULT_STACKS_CFG_PATH))
        args = parser.parse_args()

        return args

    def load_stacks(self, default_config_path, stackcfg_dir):
        default_config = load_default_cfg(default_config_path)
        stacks = []
        stacks_config = {}
        for root, dirnames, filenames in os.walk(stackcfg_dir):
            for filename in fnmatch.filter(filenames, '*.cfg'):
                stacks.append(os.path.join(root, filename))
        for stack in stacks:
            stackcfg = deepcopy(default_config)
            stackcfg = load_stack_cfg(stack, stackcfg)
            stacks_config[stack] = stackcfg
        return stacks_config

    def check_duplicate_targets(self, stacks):
        target_branches = {}
        conflict = False
        for stack in stacks:
            stackcfg = stacks[stack]
            if 'projects' not in stackcfg or stackcfg['projects'] is None:
                continue
            for project in stackcfg['projects']:
                project_config = copy.deepcopy(stackcfg['ci_default'])
                dict_union(project_config, stackcfg['projects'][project])
                if project_config:
                    target_branch = project_config.get(
                        'target_branch',
                        'lp:{}'.format(project))
                    if target_branch in target_branches:
                        existing = target_branches[target_branch]
                        logging.error(
                            "Conflict detected: {target} defined in "
                            "{stack}:{project} and {new_stack}:{new_project})"
                            "".format(
                                target=target_branch,
                                stack=existing['stack'],
                                new_stack=stack,
                                new_project=project,
                                project=existing['project']))
                        target_branches[target_branch]['project'] = project
                        target_branches[target_branch]['project'] = project
                        target_branches[target_branch]['project'] = project
                        conflict = True
                    else:
                        target_branches[target_branch] = {
                            'stack': stack,
                            'project': project
                        }

        return conflict

    def __call__(self, default_config_path):
        """Entry point for cu2d-trigger"""
        args = self.parse_arguments()

        set_logging(args.debug)
        stacks = self.load_stacks(default_config_path, args.stackcfg_dir)
        ret = True
        ret = ret and self.check_duplicate_targets(stacks)
