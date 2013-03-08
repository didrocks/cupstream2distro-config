"""Create/Update jenkins ci and autolanding jobs for a given stack

- Reads stack configuration from YAML configuration file
- Create/updates the jenkins jobs on the server configured in the credentials
file

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
import copy
import logging
import os
import sys
from textwrap import dedent

from c2dconfigutils import (
    dict_union, load_jenkins_credentials, load_default_cfg, load_stack_cfg,
    get_jinja_environment, get_jenkins_handle, setup_job, set_logging)


class JobParameter(object):
    def __init__(self, name, value, description=''):
        self.name = name
        self.value = value
        self.description = description

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return '<JobParameter %s: %s [%s]>' % (self.name, self.value,
                                               self.description)


class UpdateCi(object):
    DEFAULT_CREDENTIALS = os.path.expanduser('~/.cu2d.cred')
    JENKINS_CI_CONFIG_NAME = 'ci-jenkins'

    # Please keep list sorted
    TEMPLATE_KEYS = [
        'autolanding_template',
        'ci_template',
        'pbuilder_template',
    ]

    # Please keep list sorted
    TEMPLATE_CONTEXT_KEYS = [
        'archive_artifacts',
        'build_timeout',
        'concurrent_jenkins_builds',
        'configuration',
        'contact_email',
        'disabled',
        'fasttrack',
        'hook_source',
        'landing_job',
        'node_label',
        'parallel_jobs',
        'postbuild_job',
        'publish',
        'publish_coverage',
        'publish_junit',
        'priority',
        'team',
        'use_description_for_commit',
    ]

    DEFAULT_HOOK_LOCATION = '/tmp/$JOB_NAME-hooks'
    ACQUIRE_HOOK_SOURCE_TEMPLATE = "jenkins-templates/acquire-hooks.sh.tmpl"

    def parse_arguments(self):
        parser = argparse.ArgumentParser(
            description='Create/Update the configuration of the Jenkins ci '
            'and autolanding jobs for a stack.',
            epilog=dedent("""\
                Example:
                To update the indicator stack run the following command:
                    $ ./cu2d-update-ci -dU ./etc/indicators-head.cfg
                """),
            formatter_class=argparse.RawTextHelpFormatter)
        parser.add_argument('-C', '--credentials', metavar='CREDENTIALFILE',
                            default=self.DEFAULT_CREDENTIALS,
                            help='use Jenkins and load credentials from '
                            'CREDENTIAL FILE\n(default: %s)' %
                            self.DEFAULT_CREDENTIALS)
        parser.add_argument('-U', '--update-jobs', action='store_true',
                            default=False,
                            help='by default only new jobs are added. This '
                            'option enables \nupdate of existing jobs from '
                            'configuration template.')
        parser.add_argument('-d', '--debug', action='store_true',
                            default=False,
                            help='enable debug mode')
        parser.add_argument('stackcfg', help='Path to a configuration file '
                            'for the stack')
        return parser.parse_args()

    def add_parameter(self, ctx, name, value):
        """ Adds a parameter to the template context

        :param ctx: template context to store parameter
        :param name: name of the parameter
        :param value: value assigned to the parameter
        """
        parameter = JobParameter(name, value)
        ctx['parameter_list'].append(parameter)

    def process_project_config(self, project_name, project_config):
        """ Generates the template context from a project configuration

        :param project_name: the project name from the stack definition
        :param project_config: dictionary containing the project definition
        :param configurations: build configurations found in the
        project_config

        :return ctx: template context dict generated from the project_config
        """
        ctx = dict()
        parameters = dict()
        for key in project_config:
            data = project_config[key]

            # Process all the special keys first
            if key == 'hook_source':
                ctx['hook_location'] = self.DEFAULT_HOOK_LOCATION
                hook_script = open(
                    self.ACQUIRE_HOOK_SOURCE_TEMPLATE, 'r').read()
                hook_script = hook_script.format(
                    DEFAULT_HOOK_LOCATION=self.DEFAULT_HOOK_LOCATION)
                ctx['acquire_hook_script'] = hook_script
                parameters[key] = data
            elif key in self.TEMPLATE_KEYS:
                pass
            elif key in self.TEMPLATE_CONTEXT_KEYS:
                # These are added as ctx keys only
                ctx[key] = data
            else:
                # Everything else is added as a parameter and a ctx key
                parameters[key] = data

        if 'target_branch' not in parameters:
            parameters['target_branch'] = "lp:" + project_name
            logging.info("adding default target_branch: %s" %
                         parameters['target_branch'])
        else:
            logging.info("using target_branch: %s" %
                         parameters['target_branch'])

        ctx['parameter_list'] = []
        for parameter in parameters:
            ctx[parameter] = parameters[parameter]
            self.add_parameter(ctx, parameter, parameters[parameter])
        return ctx

    def generate_jobs(self, job_list, project_name, job_type, job_config,
                      job_template, build_template):
        """ Generates the main job and builder jobs for a given project

        :param job_list: list to hold the generated jobs
        :param project_name: the project name from the stack definition
        :param job_type: 'ci' or 'autolanding'
        :param job_config: dictionary containing the job definition
        :param job_template: template used to define the main job
        :param build_template: template used to define the build jobs
        """
        job_name = "-".join([project_name, job_type])
        build_list = []
        if 'configurations' in job_config:
            configurations = job_config.pop('configurations')
            for config_name in configurations:
                build_config = copy.deepcopy(job_config)
                build_config['configuration'] = config_name

                data = copy.deepcopy(configurations[config_name])
                if 'template' in data:
                    template = data.pop('template')
                else:
                    template = build_template
                dict_union(build_config, data)

                ctx = self.process_project_config(project_name, build_config)

                build_name = '-'.join([project_name, config_name, job_type])
                build_list.append(build_name)
                job_list.append({'name': build_name,
                                 'template': template,
                                 'ctx': ctx})

        ctx = self.process_project_config(project_name, job_config)

        ctx['builder_list'] = ','.join(build_list)
        job_list.append({'name': job_name,
                         'template': job_template,
                         'ctx': ctx})

    def process_stack(self, job_list, stack):
        """ Process the projects with the stack

        :param job_list: list to hold the generated jobs
        :param stack: dictionary with configuration of the stack
        """
        # prepare by project
        for project_name in stack['projects']:
            # Merge the default config with the project specific config
            project_config = copy.deepcopy(stack['ci_default'])
            dict_union(project_config, stack['projects'][project_name])

            ci_template = None
            autolanding_template = None
            ci_only_dict = dict()
            autolanding_only_dict = dict()

            # Extract the ci, autolanding or build specific items to make the
            # project configuration purely generic.
            if 'ci' in project_config:
                ci_only_dict = project_config.pop('ci')
            if 'autolanding' in project_config:
                autolanding_only_dict = project_config.pop('autolanding')
            if 'ci_template' in project_config:
                ci_template = project_config.pop('ci_template')
            if 'autolanding_template' in project_config:
                autolanding_template = project_config.pop(
                    'autolanding_template')
            if 'build_template' in project_config:
                build_template = project_config.pop('build_template')

            # Create ci job, add back in the ci dict
            if ci_template:
                ci_dict = copy.deepcopy(project_config)
                if ci_only_dict is not None:
                    dict_union(ci_dict, ci_only_dict)
                self.generate_jobs(job_list, project_name, 'ci', ci_dict,
                                   ci_template, build_template)

            # Create autolanding job, add back in the autolanding dict
            if autolanding_template:
                autolanding_dict = copy.deepcopy(project_config)
                if autolanding_only_dict is not None:
                    dict_union(autolanding_dict, autolanding_only_dict)
                self.generate_jobs(job_list, project_name, 'autolanding',
                                   autolanding_dict, autolanding_template,
                                   build_template)

    def update_jenkins(self, jenkins_handle, jjenv, stack, update=False):
        """ Add/update jenkins jobs

        :param stack: dictionary with configuration of the stack
        :param update: Update existing jobs if true

        :return: True on success
        """
        if stack['projects']:
            job_list = []
            self.process_stack(job_list, stack)
            for job in job_list:
                setup_job(jenkins_handle, jjenv, job['name'], job['template'],
                          job['ctx'], update)
        return True

    def __call__(self, default_config_path):
        """Entry point for cu2d-update-ci"""
        args = self.parse_arguments()
        set_logging(args.debug)

        default_config = load_default_cfg(default_config_path)
        stackcfg = load_stack_cfg(args.stackcfg, default_config)
        if not stackcfg:
            logging.error('Stack configuration failed to load. Aborting!')

        credentials = None
        if args.credentials:
            credentialsfile = args.credentials
            credentials = load_jenkins_credentials(
                os.path.expanduser(credentialsfile),
                self.JENKINS_CI_CONFIG_NAME)
            if not credentials:
                logging.error('Credentials not found. Aborting!')
                sys.exit(1)
            jenkins_handle = get_jenkins_handle(credentials)
            if not jenkins_handle:
                logging.error('Could not acquire connection to jenkins. ' +
                              'Aborting!')
                sys.exit(1)
            jjenv = get_jinja_environment(default_config_path, stackcfg)
            if not self.update_jenkins(jenkins_handle, jjenv,
                                       stackcfg, args.update_jobs):
                logging.error('Failed to configure jenkins jobs. Aborting!')
                sys.exit(2)
