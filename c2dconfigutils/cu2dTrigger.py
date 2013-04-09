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

from c2dconfigutils import (
    dict_union, load_default_cfg, load_stack_cfg, set_logging,
    get_ci_base_job_name)


class JobTrigger(object):
    DEFAULT_PLUGIN_PATH = '/var/lib/jenkins/jenkins-launchpad-plugin/'

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
        parser.add_argument('stackcfg',
                            help='Path to a configuration file for the stack')
        return parser.parse_args()

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

    def process_stack(self, stack):
        """ Generate a list of job triggers from the projects within a stack

        :param stack: dictionary with configuration of the stack
        :return trigger_list: list of dicts containing the job trigger details
        """
        trigger_list = []
        # The 'to_transition' section is used to hold projects that
        # are not yet prepared for the daily-release process.
        # However, ci and autolanding is still needed.
        for section_name in ['projects', 'to_transition']:
            project_section = stack.get(section_name, [])
            if project_section is None:
                continue
            for project_name in project_section:
                project_config = copy.deepcopy(stack['ci_default'])
                dict_union(project_config, stack[section_name][project_name])

                for job_type in ['ci', 'autolanding']:
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

    def __call__(self, default_config_path):
        """Entry point for cu2d-trigger"""
        args = self.parse_arguments()

        set_logging(args.debug)
        default_config = load_default_cfg(default_config_path)
        stackcfg = load_stack_cfg(args.stackcfg, default_config)
        if not stackcfg:
            logging.error('Stack configuration failed to load. Aborting!')
            return 1
        trigger_list = []
        if stackcfg['projects']:
            trigger_list = self.process_stack(stackcfg)

        lock_name = self._get_lock_name(args.stackcfg)
        for trigger in trigger_list:
            self.trigger_job(args.plugin_path, trigger, lock_name)
