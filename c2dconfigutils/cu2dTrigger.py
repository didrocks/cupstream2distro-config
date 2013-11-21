"""Trigger ci and autolanding jobs for a given stack

- Reads stack configuration from YAML configuration file
- Triggers jenkins jobs from branch and job details

"""
# Copyright (C) 2013, Canonical Ltd (http://www.canonical.com/)
#
# Author: Francis Ginther <francis.ginther@canonical.com>
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
import subprocess
import fnmatch
from copy import deepcopy

from c2dconfigutils import (
    dict_union, load_default_cfg, load_stack_cfg, set_logging,
    get_ci_base_job_name)


class JobTrigger(object):
    DEFAULT_PLUGIN_PATH = '/iSCSI/jenkins/jenkins-launchpad-plugin/'
    DEFAULT_STACKS_CFG_PATH = '../stacks/'

    def parse_arguments(self):
        """ Parses the command line arguments

        return args: the parsed arguments
        """
        parser = argparse.ArgumentParser(
            description='''Trigger jenkins jobs ci and autolanding jobs from
            stack config''')
        parser.add_argument('-p', '--plugin-path',
                            default=self.DEFAULT_PLUGIN_PATH,
                            help='''specify the path to the
                            jenkins-launchpad-plugin tools (default: %s)''' %
                            self.DEFAULT_PLUGIN_PATH)
        parser.add_argument('-d', '--debug', action='store_true',
                            default=False, help='enable debug mode')
        parser.add_argument('-D', '--stackcfg-dir',
                            default=self.DEFAULT_STACKS_CFG_PATH,
                            help='Path to directory with stacks definition. ' +
                            'Useful when using -c or -l ' +
                            '(default: {}).'.format(
                                self.DEFAULT_STACKS_CFG_PATH))
        parser.add_argument('-b', '--branch',
                            default=None,
                            help='target source branch to search')
        parser.add_argument('-c', '--trigger-ci', action='store_true',
                            default=False,
                            help='trigger ci jobs')
        parser.add_argument('-l', '--trigger-autolanding', action='store_true',
                            default=False,
                            help='Trigger autolanding jobs')
        parser.add_argument('stackcfg', nargs='?',
                            help='Path to a configuration file for the stack',
                            default=None)
        args = parser.parse_args()

        if not args.stackcfg and not args.branch:
            parser.error('Either -b/--branch or stackcfg must be defined')
        if not args.trigger_ci and not args.trigger_autolanding:
            parser.error('Must specify -c/--trigger-ci or '
                         '-l/--trigger-autolanding or both')
        return args

    def generate_trigger(self, project_name, project_config, job_type):
        """ Generate a job trigger from a single project definition

        :param project_name: name of the project as defined in the stack
        :param project_config: dictionary containing the project definition
        :return trigger: dictionary containing the job trigger details
        """
        options = []
        job_base_name = get_ci_base_job_name(project_name, project_config)
        name = '-'.join([job_base_name, job_type])
        branch = project_config.get('target_branch', 'lp:' + project_name)
        if job_type is 'autolanding':
            options.append('--autoland')
            if project_config.get('fasttrack', False):
                options.append('--fasttrack')
        else:
            options.append('--trigger-ci')

        return {'name': name,
                'branch': branch,
                'options': options}

    def process_stack(self, stack, trigger_types):
        """ Generate a list of job triggers from the projects within a stack

        :param stack: dictionary with configuration of the stack
        :return trigger_list: list of dicts containing the job trigger details
        """
        trigger_list = []
        for section_name in ['projects']:
            project_section = stack.get(section_name, [])
            if project_section is None:
                continue
            for project_name in project_section:
                project_config = copy.deepcopy(stack['ci_default'])
                dict_union(project_config, stack[section_name][project_name])

                for job_type in trigger_types:
                    if project_config.get(job_type + '_template', None):
                        trigger_list.append(self.generate_trigger(
                            project_name, project_config, job_type))
        return trigger_list

    def trigger_job(self, plugin_path, trigger, lock_name):
        """ Performs the actual process call on the given trigger

        :param plugin_path: path to the jenkins job launching plugin
        :param trigger: dictionary containing the job trigger details
        """
        logging.debug('Triggering {}'.format(trigger['branch']))
        trigger_call = [os.path.join(plugin_path, 'launchpadTrigger.py'),
                        '--lock-name={}'.format(lock_name),
                        '--branch={}'.format(trigger['branch']),
                        '--job={}'.format(trigger['name'])]
        trigger_call.extend(trigger['options'])
        logging.debug(' '.join(trigger_call))
        try:
            output = subprocess.check_call(trigger_call, cwd=plugin_path,
                                           stderr=subprocess.STDOUT)
            logging.debug(output)
        except subprocess.CalledProcessError as e:
            logging.error('Command %s returned non-zero exit status %d',
                          e.cmd, e.returncode)

    def _get_lock_name(self, stack):
        stack = os.path.normpath(stack)
        result = ''
        head, result = os.path.split(stack)
        if head:
            head, tail = os.path.split(head)
            return '{}-{}'.format(tail, result)
        else:
            return result

    def trigger_stack(self, default_config, stackcfg, plugin_path,
                      trigger_types):
        lock_name = self._get_lock_name(stackcfg)
        stackcfg = load_stack_cfg(stackcfg, default_config)
        if not stackcfg:
            logging.error('Stack configuration failed to load. Aborting!')
            return 1
        trigger_list = []
        if stackcfg['projects']:
            trigger_list = self.process_stack(stackcfg, trigger_types)

        for trigger in trigger_list:
            self.trigger_job(plugin_path, trigger, lock_name)
        return 0

    def get_trigger_for_target(self, default_config, target_branch,
                               stackcfg_dir, trigger_type):
        stacks = []
        for root, dirnames, filenames in os.walk(stackcfg_dir):
            for filename in fnmatch.filter(filenames, '*.cfg'):
                stacks.append(os.path.join(root, filename))
        for stack in stacks:
            stackcfg = deepcopy(default_config)
            stackcfg = load_stack_cfg(stack, stackcfg)
            if 'projects' not in stackcfg or not stackcfg['projects']:
                continue

            for project in stackcfg['projects']:
                project_config = copy.deepcopy(stackcfg['ci_default'])
                dict_union(project_config, stackcfg['projects'][project])
                if project_config:
                    project_target_branch = project_config.get(
                        'target_branch',
                        'lp:{}'.format(project))
                    if target_branch == project_target_branch:
                        trigger = self.generate_trigger(project,
                                                        project_config,
                                                        trigger_type)
                        return trigger
        logging.error('No configuration found for {}.'.format(target_branch))
        return None

    def trigger_project(self, plugin_path, default_config, trigger_branch,
                        stackcfg_dir, trigger_types):

        for job_type in trigger_types:
            trigger = self.get_trigger_for_target(default_config,
                                                  trigger_branch,
                                                  stackcfg_dir, job_type)
        if not trigger:
            return 1
        self.trigger_job(plugin_path, trigger, lock_name='target-branch')
        return 0

    def __call__(self, default_config_path):
        """Entry point for cu2d-trigger"""
        args = self.parse_arguments()

        set_logging(args.debug)
        default_config = load_default_cfg(default_config_path)
        trigger_types = []
        if args.trigger_autolanding:
            trigger_types.append('autolanding')
        if args.trigger_ci:
            trigger_types.append('ci')
        if args.stackcfg:
            return self.trigger_stack(default_config,
                                      args.stackcfg,
                                      args.plugin_path,
                                      trigger_types)
        if args.branch and args.stackcfg_dir:
            return self.trigger_project(args.plugin_path, default_config,
                                        args.branch, args.stackcfg_dir,
                                        trigger_types)
        logging.error('Invalid arguments')
        return -1
