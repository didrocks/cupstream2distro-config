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
import time
from textwrap import dedent

from c2dconfigutils import (
    dict_union, load_jenkins_credentials, load_default_cfg, load_stack_cfg,
    get_jinja_environment, get_jenkins_handle, setup_job, set_logging,
    get_ci_base_job_name, disable_job, is_job_disabled, is_job_idle)


class JobParameter(object):
    def __init__(self, name, value, description=''):
        self.name = name
        self.value = value
        self.description = description

    def __repr__(self):
        return '<JobParameter %s: %s [%s]>' % (self.name, self.value,
                                               self.description)

    def __eq__(self, other):
        return (self.name == other.name and
                self.value == other.value and
                self.description == other.description)


class UpdateCi(object):
    DEFAULT_CREDENTIALS = os.path.expanduser('~/.cu2d.cred')
    JENKINS_CI_CONFIG_NAME = 'ci-jenkins'
    DEPLOY_WAIT = 10

    # Please keep list sorted
    TEMPLATE_CONTEXT_KEYS = [
        'archive_artifacts',
        'build_timeout',
        'concurrent_jenkins_builds',
        'configuration',
        'contact_email',
        'days_to_keep_builds',
        'disabled',
        'fasttrack',
        'hook_source',
        'irc_notification',
        'irc_channel',
        'landing_job',
        'local_archive_host',
        'local_archive_login',
        'local_archive_tmp',
        'log_rotator',
        'node_label',
        'num_to_keep_builds',
        'parallel_jobs',
        'postbuild_job',
        'publish',
        'publish_coverage',
        'publish_junit',
        'priority',
        'rebuild',
        'team',
        'use_description_for_commit',
        'use_stack_ppa',
    ]

    DEFAULT_HOOK_LOCATION = '/tmp/$JOB_NAME-hooks'
    ACQUIRE_HOOK_SOURCE_TEMPLATE = 'jenkins-templates/acquire-hooks.sh.tmpl'
    AGGREGATE_TESTS_TEMPLATE = 'jenkins-templates/aggregate-tests.sh.tmpl'

    GENERATED_HOOK_TEMPLATE = 'D09add_ppa~{}'

    def __init__(self):
        self.default_config_path = None

    def _get_build_script(self, template, formatting):
        script = open(os.path.join(self.default_config_path,
                                   template), 'r').read()
        return script.format(**formatting)

    def parse_arguments(self):
        parser = argparse.ArgumentParser(
            description='''Create/Update the configuration of the Jenkins ci
            and autolanding jobs for a stack.''',
            epilog=dedent('''\
                Example:
                To update the indicator stack run the following command:
                    $ ./cu2d-update-ci -d ./etc/indicators-head.cfg
                To update a project in the indicator stack run:
                    $ ./cu2d-update-ci -p aproject ./etc/indicators-head.cfg
                To delete orphaned release(s) in a project from jenkins run:
                (Will delete matching jobs after asking)
                    $ ./cu2d-update-ci -p aproject -o raring -c saucy
                    $ ./cu2d-update-ci -p aproject -o i386 -c amd64
                    $ ./cu2d-update-ci -p aproject -o armel -c armhf
                To delete orphaned release(s) in a project from jenkins '''
                '''without a y/n prompt run:
                (** dangerous ** Will delete matching jobs on jenkins '''
                '''without asking)
                    $ ./cu2d-update-ci -p aproject -o raring -c saucy -r
                '''),
            formatter_class=argparse.RawTextHelpFormatter)
        parser.add_argument('-C', '--credentials', metavar='CREDENTIALFILE',
                            default=self.DEFAULT_CREDENTIALS,
                            help='use Jenkins and load credentials from '
                            'CREDENTIAL FILE\n(default: %s)' %
                            self.DEFAULT_CREDENTIALS)
        parser.add_argument('-d', '--debug', action='store_true',
                            default=False,
                            help='enable debug mode')
        parser.add_argument('-p', '--project', action='store',
                            dest='project',
                            help='the name of a project in a stack '
                            'to update')
        parser.add_argument('-o', '--orphan-release', action='store',
                            dest='orphan_release')
        parser.add_argument('-c', '--current-release', action='store',
                            dest='current_release')
        parser.add_argument('-r', '--remove', action='store_true',
                            default=False)
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

    def get_rebuild_job(self, stack, project_name):
        """ Generates the rebuild job name for a project

        :param stack: the original stack dictionary
        :param project_name: the project name to lookup
        :return job_name: the rebuild job name for the requested project
        """
        if project_name in stack['projects']:
            project_config = stack['projects'][project_name]
            if project_config:
                job_name = '{}-rebuild'.format(
                    get_ci_base_job_name(project_name, project_config))
            else:
                job_name = '{}-rebuild'.format(project_name)
        else:
            # Allow for a user specified rebuild job
            job_name = project_name
        return job_name

    def process_project_config(self, project_name, project_config,
                               job_data, builder_job=False):
        """ Generates the template context from a project configuration

        :param project_name: the project name from the stack definition
        :param project_config: dictionary containing the project definition
        :param job_data: supplemental data for job generation

        :return ctx: template context dict generated from the project_config
        """
        ctx = dict()
        parameters = dict()

        # Patch in the hook for the stack ppa
        if job_data.get('stack_ppa', False):
            stack_ppa_hook = self.GENERATED_HOOK_TEMPLATE.format(
                job_data['stack_ppa'].replace('/', '~'))
            if project_config.get('use_stack_ppa', False):
                if project_config.get('hooks', False):
                    project_config['hooks'] = ' '.join(
                        [stack_ppa_hook, project_config['hooks']])
                else:
                    project_config['hooks'] = stack_ppa_hook

        # Rename hooks parameter for builder jobs
        if builder_job and 'hooks' in project_config:
            # The hooks parameter used by the builder job must not have
            # the same name as the parent job. Otherwise, the builder job
            # will always inherit the hooks from the parent and builder
            # specific hooks specified in the stack file will be ignored.
            project_config['builder_hooks'] = project_config['hooks']

        for key in project_config:
            data = project_config[key]

            # Process all the special keys first
            if key == 'hook_source':
                ctx['hook_location'] = self.DEFAULT_HOOK_LOCATION
                formatting = {'DEFAULT_HOOK_LOCATION':
                              self.DEFAULT_HOOK_LOCATION}
                script = self._get_build_script(
                    self.ACQUIRE_HOOK_SOURCE_TEMPLATE,
                    formatting)
                ctx['acquire_hook_script'] = script
                parameters[key] = data
            elif key == 'aggregate_tests':
                # aggregate_tests can be used to specify a specific
                # job name or a configuration from which to pull artifacts.
                if not data:
                    # This allows a project to undefine a default value
                    continue
                build_lookup = job_data.get('build_lookup', {})
                in_list = data.split()
                out_list = []
                for agg_job in in_list:
                    # If it's a configuration, substitute the actual job name.
                    if agg_job in build_lookup:
                        out_list.append(build_lookup[agg_job])
                    else:
                        out_list.append(agg_job)

                formatting = {'DOWNSTREAM_BUILD_JOB': ' '.join(out_list)}
                script = self._get_build_script(self.AGGREGATE_TESTS_TEMPLATE,
                                                formatting)
                ctx['aggregate_tests_script'] = script
            elif key == 'rebuild':
                # Only support manually specified rebuild jobs
                if data:
                    rebuild_list = []
                    for rebuild_project in data.split(','):
                        rebuild_job = self.get_rebuild_job(
                            job_data['stack'], rebuild_project.strip())
                        rebuild_list.append(rebuild_job)
                    ctx['rebuild'] = ','.join(rebuild_list)

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
        # add project name as well
        ctx['project_name'] = project_name
        self.add_parameter(ctx, 'project_name', project_name)
        return ctx

    def generate_jobs(self, job_list, project_name, job_type, build_type,
                      job_config, job_template, build_template, job_data):
        """ Generates the main job and builder jobs for a given project

        :param job_list: list to hold the generated jobs
        :param project_name: the project name from the stack definition
        :param job_type: parent job - 'ci', 'autolanding' or 'rebuild'
        :param build_type: builder job - 'ci' or 'autolanding'
        :param job_config: dictionary containing the job definition
        :param job_template: template used to define the main job
        :param build_template: template used to define the build jobs
        :param job_data: supplemental data for job generation
        """

        job_base_name = get_ci_base_job_name(project_name, job_config)
        job_name = "-".join([job_base_name, job_type])
        build_list = []
        job_data['build_lookup'] = {}
        if 'configurations' in job_config:
            configurations = job_config.pop('configurations')
            for config_name in configurations:
                build_config = copy.deepcopy(job_config)
                build_config['configuration'] = config_name

                data = copy.deepcopy(configurations[config_name])
                # if the configuration doesn't contain any data it means
                # the user doesn't want any job for it
                if not data:
                    continue
                if 'template' in data:
                    template = data.pop('template')
                else:
                    template = build_template
                # A pre-defined job can be specified as a build task by
                # naming the configuration to match the job name and
                # setting the template value to False or None.
                if not template or template is None:
                    build_list.append(config_name)

                else:
                    build_name = '-'.join([job_base_name, config_name,
                                           build_type])
                    build_list.append(build_name)
                    if job_type == 'rebuild':
                        # For rebuild jobs, the autolanding builder jobs will
                        # be reused. So all that is needed is the build_list.
                        continue
                    dict_union(build_config, data)
                    ctx = self.process_project_config(project_name,
                                                      build_config, job_data,
                                                      builder_job=True)
                    job_data['build_lookup'][config_name] = build_name
                    job_list.append({'name': build_name,
                                     'template': template,
                                     'ctx': ctx,
                                     'deployed': False,
                                     'parents': [job_name]})

        ctx = self.process_project_config(project_name, job_config, job_data)

        ctx['builder_list'] = ','.join(build_list)
        if job_type == 'rebuild':
            for job in job_list:
                if job['name'] in build_list:
                    job['parents'].append(job_name)
        job_list.append({'name': job_name,
                         'template': job_template,
                         'ctx': ctx,
                         'deployed': False,
                         'parents': None})

    def prepare_project(self, job_list, stack, project_name):
        """Prepare by project

        :param job_list: list to hold the generated jobs
        :param stack: dictionary with configuration of the stack
        :param project_name: a project to update in the stack
        """
        # If the stack has a ppa value defined, it needs to be added as a
        # hook to each project
        stack_ppa = stack.get('ppa', False)
        if stack_ppa == "null":
            stack_ppa = False
        job_data = {'stack': stack,
                    'stack_ppa': stack_ppa}

        # Merge the default config with the project specific config
        project_config = copy.deepcopy(stack['ci_default'])
        dict_union(project_config, stack['projects'][project_name])

        ci_template = None
        autolanding_template = None
        rebuild_template = None
        ci_only_dict = dict()
        autolanding_only_dict = dict()
        rebuild_only_dict = dict()

        # Extract the ci, autolanding or build specific items to make the
        # project configuration purely generic.
        if 'ci' in project_config:
            ci_only_dict = project_config.pop('ci')
        if 'autolanding' in project_config:
            autolanding_only_dict = project_config.pop('autolanding')
            rebuild_only_dict = copy.deepcopy(autolanding_only_dict)
        if 'ci_template' in project_config:
            ci_template = project_config.pop('ci_template')
        if 'autolanding_template' in project_config:
            autolanding_template = project_config.pop('autolanding_template')
        if 'rebuild_template' in project_config:
            rebuild_template = project_config.pop('rebuild_template')
        if 'build_template' in project_config:
            build_template = project_config.pop('build_template')

        # Create ci job, add back in the ci dict
        if ci_template:
            ci_dict = copy.deepcopy(project_config)
            if ci_only_dict is not None:
                dict_union(ci_dict, ci_only_dict)
            self.generate_jobs(job_list, project_name, 'ci', 'ci', ci_dict,
                               ci_template, build_template, job_data)

        # Create autolanding job, add back in the autolanding dict
        if autolanding_template:
            autolanding_dict = copy.deepcopy(project_config)
            if autolanding_only_dict is not None:
                dict_union(autolanding_dict, autolanding_only_dict)
            self.generate_jobs(job_list, project_name, 'autolanding',
                               'autolanding',
                               autolanding_dict, autolanding_template,
                               build_template, job_data)

        # Create rebuild job, add in the rebuild dict
        if rebuild_template:
            rebuild_dict = copy.deepcopy(project_config)
            if rebuild_only_dict is not None:
                dict_union(rebuild_dict, rebuild_only_dict)
            self.generate_jobs(job_list, project_name, 'rebuild',
                               'autolanding',
                               rebuild_dict, rebuild_template,
                               build_template, job_data)

    def process_stack(self, job_list, stack, target_project=None):
        """ Process the projects with the stack

        :param job_list: list to hold the generated jobs
        :param stack: dictionary with configuration of the stack
        :param target_project: a project to update in the stack
        """
        if target_project is None:
            for project_name in stack['projects']:
                self.prepare_project(job_list, stack, project_name)
            return True
        elif target_project in stack['projects']:
            self.prepare_project(job_list, stack, target_project)
            return True
        else:
            logging.error("project: {} was not found".format(target_project))
            return False

    def orphan_search_jenkins(self, jenkins_handle, stack,
                              current_release=None, target_project=None,
                              orphan_release=None, remove=False):
        """search jenkins for projects with orphaned jobs and remove the job

        :param jenkins_handle: jenkins access handle
        :param stack: dictionary with configuration of the stack
        :param target_project: target a single project in stack
        :param current_release: the latest ubuntu development release name
        :param orphan_release: ubuntu release that has been orphaned by project
        :param remove: delete all orphaned jobs found

        """
        if target_project is None:
            logging.error("target_project cannot be None")
            return False
        else:
            if stack['projects']:
                #get all jobs from jenkins
                get_jobs = jenkins_handle.get_jobs()
                jenk_list = [job['name'] for job in get_jobs]

                #get all jobs from the project stack
                stack_list = []
                self.process_stack(stack_list, stack, target_project)
                stack_list = [job['name'] for job in stack_list]

                #remove jobs from current project stack from jenkins list
                jenk_list = list(set(jenk_list) - set(stack_list))

                #update the project list with potentially abandoned jobs
                stack_list = [item.replace(current_release, orphan_release)
                              for item in stack_list]

                #make a list of the potentially abandon jobs
                orphan_list = list(set(stack_list) & set(jenk_list))
                for job in orphan_list:
                    logging.warning('Potential orphan job found: '
                                    '{}'.format(job))

                def delete_jobs():
                    logging.info("Deleting Abandoned jobs")
                    for job in orphan_list:
                        jenkins_handle.delete_job(job)

                def get_answer():
                        answer = raw_input("Do you want to delete orphaned "
                                           "jobs?\n  Yes or No\nType No if "
                                           "you are not sure: ")
                        answer.lower()
                        if answer == "yes" or answer == "y":
                                delete_jobs()
                        elif answer == "no" or answer == "n":
                            logging.info("Abandoned jobs remain on jenkins")
                        else:
                            get_answer()
                if orphan_list:
                    if remove:
                        delete_jobs()
                    else:
                        get_answer()
                else:
                    logging.info('No abandoned jobs found')
                return True

    def are_children_deployed(self, job_list, parent_name):
        """Returns true of all of a parents' children have been deployed

        :param job_list: list of alls jobs set to deploy
        :param parent_name: the name of the parent job

        :return deployed: True if children are deployed, otherwise False
        """
        for job in job_list:
            if ((job['parents'] and parent_name in job['parents']) and
                    (not job['deployed'])):
                return False
        return True

    def are_jobs_idle(self, jenkins_handle, job_name_list):
        """Returns true of all jobs in the given list are idle

        :param jenkins_handle: jenkins access handle
        :param job_name_list: list of job names to check

        :return deployed: True if children are deployed, otherwise False
        """
        for job_name in job_name_list:
            if not is_job_idle(jenkins_handle, job_name):
                return False
        return True

    def deploy_jobs(self, jenkins_handle, jjenv, job_list):
        """deploys the job list to the jenkins server without updating
        actively running jobs

        Only the parent jobs are disabled before being updated. This is
        because child jobs for a running parent job could be in the queue,
        these jobs would be purged if the child job was disabled. Disabling
        the parent job prevents new builds from starting.

        Child jobs are only updated once their parent(s) have been disabled
        and idled. This is safe as long as the child jobs aren't executed
        by something outside of the stack generated jobs.

        Once all of the child jobs are updated, the parent(s) can be updated.
        Updating the job will enable it (unless the job is disabled in the
        stack definition).

        :param jenkins_handle: jenkins access handle
        :param jjenv: jinja2 template environment handle
        :param job_list: list of jobs to deploy

        :return wait_list: list of jobs not yet deployed
        """
        wait_list = []
        # Parent jobs must be processed first so that they can be disabled
        # before the child jobs are deployed. Otherwise, a child job could
        # be deployed just prior to an undeployed parent job being triggered.
        # These jobs would then execute out of sync.
        for job in job_list:
            if job['parents'] is None and not job['deployed']:
                logging.info("Attempting to deploy: %s" % job['name'])
                if not is_job_disabled(jenkins_handle, job['name']):
                    logging.info("Disabling: %s" % job['name'])
                    disable_job(jenkins_handle, job['name'])
                if self.are_children_deployed(job_list, job['name']):
                    if is_job_idle(jenkins_handle, job['name']):
                        setup_job(jenkins_handle, jjenv, job['name'],
                                  job['template'], job['ctx'], update=True)
                        job['deployed'] = True
                    else:
                        wait_list.append(job['name'])
                else:
                    wait_list.append(job['name'])
        for job in job_list:
            if job['parents'] is not None and not job['deployed']:
                logging.info("Attempting to deploy: %s" % job['name'])
                if self.are_jobs_idle(jenkins_handle, job['parents']):
                    setup_job(jenkins_handle, jjenv, job['name'],
                              job['template'], job['ctx'], update=True)
                    job['deployed'] = True
                else:
                    wait_list.append(job['name'])
        return wait_list

    def update_jenkins(self, jenkins_handle, jjenv, stack,
                       target_project=None):
        """ Add/update jenkins jobs

        :param jenkins_handle: jenkins access handle
        :param jjenv: jinja2 template environment handle
        :param stack: dictionary with configuration of the stack

        :return: True on success
        """
        if stack['projects']:
            job_list = []
            self.process_stack(job_list, stack, target_project)
            while True:
                wait_list = self.deploy_jobs(jenkins_handle, jjenv, job_list)
                if len(wait_list) > 0:
                    logging.info("Deployed %d of %d jobs" %
                                 (len(job_list) - len(wait_list),
                                  len(job_list)))
                    logging.info("Waiting on: %s" % (", ".join(wait_list)))
                    logging.info("Sleeping for {} seconds".format(
                        self.DEPLOY_WAIT))
                    time.sleep(self.DEPLOY_WAIT)
                else:
                    logging.info("All jobs deployed")
                    break
        return True

    def __call__(self, default_config_path):
        """Entry point for cu2d-update-ci"""
        self.default_config_path = default_config_path

        args = self.parse_arguments()
        set_logging(args.debug)

        default_config = load_default_cfg(default_config_path)
        stackcfg = load_stack_cfg(args.stackcfg, default_config)
        if not stackcfg:
            logging.error('Stack configuration failed to load. Aborting!')
            return 1

        credentials = None
        if args.credentials:
            credentialsfile = args.credentials
            credentials = load_jenkins_credentials(
                os.path.expanduser(credentialsfile),
                self.JENKINS_CI_CONFIG_NAME)
            if not credentials:
                logging.error('Credentials not found. Aborting!')
                return 1
            jenkins_handle = get_jenkins_handle(credentials)
            if not jenkins_handle:
                logging.error('Could not acquire connection to jenkins. ' +
                              'Aborting!')
                return 1
            jjenv = get_jinja_environment(default_config_path, stackcfg)
            if not self.update_jenkins(jenkins_handle, jjenv, stackcfg,
                                       args.project):
                logging.error('Failed to configure jenkins jobs. Aborting!')
                return 2
            if args.orphan_release:
                if args.current_release:
                    self.orphan_search_jenkins(
                        jenkins_handle, stackcfg, args.current_release,
                        args.project, args.orphan_release, args.remove)
                else:
                    logging.error("cannot use orphan-release without "
                                  "current-release")
                return 1
        return 0
