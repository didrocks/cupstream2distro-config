from mock import (call, patch, MagicMock, Mock)
from testscenarios import TestWithScenarios
from textwrap import dedent
from unittest import TestCase

from c2dconfigutils.cu2dUpdateCi import (
    UpdateCi, JobParameter)


class TestJobParameter(TestCase):
    def test_repr(self):
        p = JobParameter('param', 'value', 'description')
        self.assertEqual('<JobParameter param: value [description]>',
                         '%s' % p)

    def test_repr_no_description(self):
        p = JobParameter('param', 'value')
        self.assertEqual('<JobParameter param: value []>',
                         '%s' % p)

    def test_eq(self):
        p = JobParameter('param', 'value', 'description')
        q = JobParameter('param', 'value', 'description')
        self.assertEqual(p, q)

    def test_not_eq(self):
        p = JobParameter('param', 'value', 'description')
        q = JobParameter('param', 'value')
        self.assertNotEqual(p, q)


class TestGetBuildScript(TestCase):
    def setUp(self):
        self.update_ci = UpdateCi()
        self.update_ci.default_config_path = 'base_path'

    def test_get_build_script(self):
        #script = "This is a {SCRIPT} to {TEST}."
        script = dedent("""\
                        #!{SHELL}
                        set -x

                        echo {MESSAGE}""")
        formatting = {'SHELL': '/bin/bash',
                      'MESSAGE': 'All is well'}
        expected = script.format(**formatting)
        with patch('c2dconfigutils.cu2dUpdateCi.open',
                   create=True) as mock_open:
            mock_open.return_value = MagicMock(spec=file)
            mock_open().read.return_value = script
            actual = self.update_ci._get_build_script('file.sh.tmpl',
                                                      formatting)
            mock_open.assert_called_with('base_path/file.sh.tmpl', 'r')
            self.assertEqual(expected, actual)


class TestAddParameter(TestCase):
    def setUp(self):
        self.update_ci = UpdateCi()

    def test_add_parameter(self):
        ctx = {'parameter_list': []}
        expected = [JobParameter('param1', 'value1'),
                    JobParameter('param2', 'value2')]
        self.update_ci.add_parameter(ctx, 'param1', 'value1')
        self.update_ci.add_parameter(ctx, 'param2', 'value2')
        self.assertEqual(expected, ctx['parameter_list'])


class TestProcessProjectConfig(TestCase):
    def setUp(self):
        self.update_ci = UpdateCi()
        self.update_ci.default_config_path = 'default'

    def _get_build_script_mock(self, template, formatting):
        test_str = 'DOWNSTREAM_BUILD_JOB = {DOWNSTREAM_BUILD_JOB}'
        return test_str.format(**formatting)

    def test_project_config_implied_target_branch(self):
        config = {}
        expected = {'target_branch': 'lp:project',
                    'project_name': 'project',
                    'parameter_list': [JobParameter('target_branch',
                                                    'lp:project'),
                                       JobParameter('project_name',
                                                    'project')]}
        actual = self.update_ci.process_project_config('project', config, {})
        self.assertEqual(expected, actual)

    def test_project_config_forced_target_branch(self):
        config = {'target_branch': 'lp:project/sub'}
        expected = {'target_branch': 'lp:project/sub',
                    'parameter_list': [JobParameter('target_branch',
                                                    'lp:project/sub'),
                                       JobParameter('project_name',
                                                    'project')],
                    'project_name': 'project'}
        actual = self.update_ci.process_project_config('project', config, {})
        self.assertEqual(expected, actual)

    def test_project_config_ctx_only(self):
        config = {'team': 'team_name'}
        expected = {'target_branch': 'lp:project',
                    'project_name': 'project',
                    'parameter_list': [JobParameter('target_branch',
                                                    'lp:project'),
                                       JobParameter('project_name',
                                                    'project')],
                    'team': 'team_name'}
        actual = self.update_ci.process_project_config('project', config, {})
        self.assertEqual(expected, actual)

    def test_project_config_parameter(self):
        config = {'some_parameter': 'some_value'}
        expected = {'target_branch': 'lp:project',
                    'some_parameter': 'some_value',
                    'project_name': 'project',
                    'parameter_list': [JobParameter('target_branch',
                                                    'lp:project'),
                                       JobParameter('some_parameter',
                                                    'some_value'),
                                       JobParameter('project_name',
                                                    'project')]}
        actual = self.update_ci.process_project_config('project', config, {})
        self.assertEqual(expected, actual)

    def test_hook_source(self):
        script = dedent("""\
                        #!/bin/bash
                        set -x

                        hook_dir={DEFAULT_HOOK_LOCATION}
                        rm -rf "$hook_dir"

                        if [ -n "$hook_source" ]; then
                            bzr branch "$hook_source" "$hook_dir"
                        else
                            mkdir "$hook_dir"
                        fi""")
        config = {'hook_source': 'lp:hooks'}
        expected = {'hook_location': '/tmp/$JOB_NAME-hooks',
                    'target_branch': 'lp:project',
                    'hook_source': 'lp:hooks',
                    'project_name': 'project',
                    'acquire_hook_script': script.format(
                        DEFAULT_HOOK_LOCATION='/tmp/$JOB_NAME-hooks'),
                    'parameter_list': [JobParameter('target_branch',
                                                    'lp:project'),
                                       JobParameter('hook_source',
                                                    'lp:hooks'),
                                       JobParameter('project_name',
                                                    'project')]}
        with patch('c2dconfigutils.cu2dUpdateCi.open',
                   create=True) as mock_open:
            mock_open.return_value = MagicMock(spec=file)
            mock_open().read.return_value = script
            actual = self.update_ci.process_project_config('project', config,
                                                           {})
            mock_open.assert_called_with(
                'default/jenkins-templates/acquire-hooks.sh.tmpl', 'r')
            self.assertEqual(expected, actual)

    def test_project_config_stack_ppa(self):
        config = {'hooks': 'my_hook'}
        job_data = {'stack_ppa': 'ppa_team/ppa_name'}
        expected = {'target_branch': 'lp:project',
                    'project_name': 'project',
                    'hooks': 'D09add_ppa~ppa_team~ppa_name my_hook',
                    'parameter_list': [
                        JobParameter('hooks',
                                     'D09add_ppa~ppa_team~ppa_name my_hook'),
                        JobParameter('target_branch',
                                     'lp:project'),
                        JobParameter('project_name',
                                     'project')]}
        actual = self.update_ci.process_project_config('project', config,
                                                       job_data)
        self.assertEqual(expected, actual)

    def test_project_config_stack_ppa_with_no_hooks(self):
        config = {'hooks': ''}
        job_data = {'stack_ppa': 'ppa_team/ppa_name'}
        expected = {'target_branch': 'lp:project',
                    'project_name': 'project',
                    'hooks': 'D09add_ppa~ppa_team~ppa_name',
                    'parameter_list': [
                        JobParameter('hooks',
                                     'D09add_ppa~ppa_team~ppa_name'),
                        JobParameter('target_branch',
                                     'lp:project'),
                        JobParameter('project_name',
                                     'project')]}
        actual = self.update_ci.process_project_config('project', config,
                                                       job_data)
        self.assertEqual(expected, actual)

    def test_project_config_stack_ppa_with_false_hooks(self):
        config = {'hooks': False}
        job_data = {'stack_ppa': 'ppa_team/ppa_name'}
        expected = {'target_branch': 'lp:project',
                    'project_name': 'project',
                    'hooks': 'D09add_ppa~ppa_team~ppa_name',
                    'parameter_list': [
                        JobParameter('hooks',
                                     'D09add_ppa~ppa_team~ppa_name'),
                        JobParameter('target_branch',
                                     'lp:project'),
                        JobParameter('project_name',
                                     'project')]}
        actual = self.update_ci.process_project_config('project', config,
                                                       job_data)
        self.assertEqual(expected, actual)

    def test_project_config_aggregate_tests(self):
        config = {'aggregate_tests': 'generic-job'}
        expected = {'target_branch': 'lp:project',
                    'project_name': 'project',
                    'aggregate_tests_script':
                    'DOWNSTREAM_BUILD_JOB = generic-job',
                    'parameter_list': [JobParameter('target_branch',
                                                    'lp:project'),
                                       JobParameter('project_name',
                                                    'project')]}
        self.update_ci._get_build_script = self._get_build_script_mock
        actual = self.update_ci.process_project_config('project', config, {})
        self.assertEqual(expected, actual)


class TestGenerateJobs(TestWithScenarios, TestCase):
    job_template = 'ci.xml.tmpl'
    build_template = 'build.xml.tmpl'

    def setUp(self):
        self.update_ci = UpdateCi()

    def test_generate_jobs_names(self):
        config = {
            'configurations': {
                'raring-amd64': {'node_label': 'pbuilder'},
                'raring-i386': {'node_label': 'pbuilder'}}}
        expected = ['foo-raring-amd64-ci',
                    'foo-raring-i386-ci',
                    'foo-ci']
        job_list = []
        self.update_ci.generate_jobs(job_list, 'foo', 'ci', config,
                                     self.job_template, self.build_template,
                                     {})
        actual = [job['name'] for job in job_list]
        self.assertEqual(expected, actual)

    def test_generate_jobs_templates(self):
        config = {
            'configurations': {
                'raring-amd64': {'node_label': 'pbuilder'},
                'raring-i386': {'node_label': 'pbuilder'}}}
        expected = ['build.xml.tmpl',
                    'build.xml.tmpl',
                    'ci.xml.tmpl']
        job_list = []
        self.update_ci.generate_jobs(job_list, 'foo', 'ci', config,
                                     self.job_template, self.build_template,
                                     {})
        actual = [job['template'] for job in job_list]
        self.assertEqual(expected, actual)

    def test_generate_jobs_template_override(self):
        config = {
            'configurations': {
                'raring-amd64': {
                    'template': 'foo.xml.tmpl'},
                'raring-i386': {
                    'template': 'bar.xml.tmpl'}}}
        expected = ['foo.xml.tmpl',
                    'bar.xml.tmpl',
                    'ci.xml.tmpl']
        job_list = []
        self.update_ci.generate_jobs(job_list, 'foo', 'ci', config,
                                     self.job_template, self.build_template,
                                     {})
        actual = [job['template'] for job in job_list]
        self.assertEqual(expected, actual)

    def test_generate_jobs_builder_list(self):
        config = {
            'configurations': {
                'raring-amd64': {'node_label': 'pbuilder'},
                'raring-i386': {'node_label': 'pbuilder'}}}
        expected = 'foo-raring-amd64-ci,foo-raring-i386-ci'
        job_list = []
        self.update_ci.generate_jobs(job_list, 'foo', 'ci', config,
                                     self.job_template, self.build_template,
                                     {})
        actual = job_list[2]['ctx']['builder_list']
        self.assertEqual(expected, actual)


class TestUpdateJenkins(TestCase):
    def setUp(self):
        self.jenkins = MagicMock()
        self.jenkins.job_exists = lambda x: False
        self.jenkins.create_job = MagicMock()
        self.tmpl = MagicMock()
        self.tmpl.render.return_value = 'template'
        self.jjenv = MagicMock()
        self.jjenv.get_template.return_value = self.tmpl
        self.update_ci = UpdateCi()

    def test_empty_stack(self):
        stack = {'projects': None}
        self.update_ci.update_jenkins(None, None, stack, None)

    def test_stack(self):
        stack = {
            'ci_default': {
                'ci_template': 'ci-config.xml.tmpl',
                'autolanding_template': 'autolanding-config.xml.tmpl',
                'build_template': 'pbuilder-config.xml.tmpl'},
            'projects': {
                'autopilot': {
                    'team': 'Autopilot Team',
                    'contact_email': 'address@email',
                    'distributions': 'raring,quantal,precise',
                    'ppa_target': 'ppa:autopilot/ppa',
                    'autolanding': {
                        'postbuild_job': 'autopilot-docs-upload',
                        'archive_artifacts': '**/output/*deb',
                        'configurations': {
                            'raring-amd64': {
                                'priority': 10000},
                            'raring-i386': {
                                'template': 'autopilot-config.xml.tmpl',
                                'node_label': 'pbuilder'}}}},
                'xpathselect': {}}}
        calls = []
        calls.append(call('autopilot-ci', 'template'))
        calls.append(call('autopilot-raring-amd64-autolanding', 'template'))
        calls.append(call('autopilot-raring-386-autolanding', 'template'))
        calls.append(call('autopilot-autolanding', 'template'))
        calls.append(call('xpathselect-ci', 'template'))
        self.update_ci.update_jenkins(self.jenkins, self.jjenv, stack)
        calls.append(call('xpathselect-autolanding', 'template'))
        self.jenkins.create_job.asser_hass_calls(calls)


class TestProcessStackIntegration(TestCase):
    '''An integration test that covers job generation from a stack.'''
    stack = {
        'stack': {
            'ci_default': {
                'ci_template': 'ci-config.xml.tmpl',
                'autolanding_template': 'autolanding-config.xml.tmpl',
                'build_template': 'pbuilder-config.xml.tmpl',
                'ci': {
                    'postbuild_job': False,
                    'concurrent_jenkins_builds': True},
                'autolanding': {
                    'priority': 1000,
                    'use_description_for_commit': False,
                    'postbuild_job': False},
                'configurations': {
                    'raring-amd64': {
                        'node_label': 'pbuilder'},
                    'raring-armhf': {
                        'node_label': 'panda-pbuilder'}},
                'priority': 100,
                'publish': True,
                'team': 'PS-QA',
                'landing_candidate': '',
                'landing_job': 'generic-land'},
            'projects': {
                'autopilot': {
                    'team': 'Autopilot Team',
                    'contact_email': 'address@email',
                    'distributions': 'raring,quantal,precise',
                    'ppa_target': 'ppa:autopilot/ppa',
                    'autolanding': {
                        'postbuild_job': 'autopilot-docs-upload',
                        'archive_artifacts': '**/output/*deb',
                        'configurations': {
                            'raring-amd64': {
                                'priority': 10000},
                            'raring-i386': {
                                'template': 'autopilot-config.xml.tmpl',
                                'node_label': 'pbuilder'}}}},
                'xpathselect': {}}}}

    def setUp(self):
        self.update_ci = UpdateCi()
        self.job_list = []
        self.target_project = None
        self.update_ci.process_stack(self.job_list, self.stack['stack'],
                                     self.target_project)

    def test_job_names(self):
        expected_name_list = ['autopilot-raring-amd64-ci',
                              'autopilot-raring-armhf-ci',
                              'autopilot-ci',
                              'autopilot-raring-amd64-autolanding',
                              'autopilot-raring-armhf-autolanding',
                              'autopilot-raring-i386-autolanding',
                              'autopilot-autolanding',
                              'xpathselect-raring-amd64-ci',
                              'xpathselect-raring-armhf-ci',
                              'xpathselect-ci',
                              'xpathselect-raring-amd64-autolanding',
                              'xpathselect-raring-armhf-autolanding',
                              'xpathselect-autolanding']
        actual_name_list = [job['name'] for job in self.job_list]
        self.assertEqual(expected_name_list, actual_name_list)

    def test_job_templates(self):
        expected_template_list = ['pbuilder-config.xml.tmpl',
                                  'pbuilder-config.xml.tmpl',
                                  'ci-config.xml.tmpl',
                                  'pbuilder-config.xml.tmpl',
                                  'pbuilder-config.xml.tmpl',
                                  'autopilot-config.xml.tmpl',
                                  'autolanding-config.xml.tmpl',
                                  'pbuilder-config.xml.tmpl',
                                  'pbuilder-config.xml.tmpl',
                                  'ci-config.xml.tmpl',
                                  'pbuilder-config.xml.tmpl',
                                  'pbuilder-config.xml.tmpl',
                                  'autolanding-config.xml.tmpl']
        actual_template_list = [job['template'] for job in self.job_list]
        self.assertEqual(expected_template_list, actual_template_list)

    def test_child_jobs(self):
        '''Verifies that the parent jobs have the expected child jobs'''
        expected = {'autopilot-ci':
                    'autopilot-raring-amd64-ci,autopilot-raring-armhf-ci',
                    'autopilot-autolanding':
                    'autopilot-raring-amd64-autolanding,' +
                    'autopilot-raring-armhf-autolanding,' +
                    'autopilot-raring-i386-autolanding',
                    'xpathselect-ci':
                    'xpathselect-raring-amd64-ci,xpathselect-raring-armhf-ci',
                    'xpathselect-autolanding':
                    'xpathselect-raring-amd64-autolanding,' +
                    'xpathselect-raring-armhf-autolanding'}
        for job in self.job_list:
            if job['name'] in expected:
                self.assertEqual(job['ctx']['builder_list'],
                                 expected[job['name']])

    def test_priority_overrides(self):
        '''Verifies overriding at autolanding and configuration levels'''
        for job in self.job_list:
            if job['name'] == 'autopilot-raring-amd64-autolanding':
                self.assertEqual(job['ctx']['priority'], 10000)
            elif job['name'].endswith('autolanding'):
                self.assertEqual(job['ctx']['priority'], 1000)
            else:
                self.assertEqual(job['ctx']['priority'], 100)

    def test_parent_child_parameters(self):
        '''Verifies that a child job has all of the parent parameters'''
        relationships = {
            'autopilot-ci': [
                'autopilot-raring-amd64-ci',
                'autopilot-raring-armhf-ci'],
            'autopilot-autolanding': [
                'autopilot-raring-amd64-autolanding',
                'autopilot-raring-armhf-autolanding',
                'autopilot-raring-i386-autolanding'],
            'xpathselect-ci': [
                'xpathselect-raring-amd64-ci',
                'xpathselect-raring-armhf-ci'],
            'xpathselect-autolanding': [
                'xpathselect-raring-amd64-autolanding',
                'xpathselect-raring-armhf-autolanding']}
        for parent in self.job_list:
            if parent['name'] in relationships:
                children = relationships[parent['name']]
                parent_params = [p for p in parent['ctx']['parameter_list']]
                for child in self.job_list:
                    if child['name'] in children:
                        child_params = [p for p in
                                        child['ctx']['parameter_list']]
                        for p in parent_params:
                            self.assertIn(p, child_params)

    def test_target_project(self):
        job_list = []
        target_project = 'autopilot'
        self.update_ci.process_stack(job_list, self.stack['stack'],
                                     target_project)
        expected_name_list = ['autopilot-raring-amd64-ci',
                              'autopilot-raring-armhf-ci',
                              'autopilot-ci',
                              'autopilot-raring-amd64-autolanding',
                              'autopilot-raring-armhf-autolanding',
                              'autopilot-raring-i386-autolanding',
                              'autopilot-autolanding']
        actual_name_list = [job['name'] for job in job_list]
        self.assertEqual(expected_name_list, actual_name_list)

    def test_target_project_invalid(self):
        job_list = []
        target_project = 'this_should_error'
        result = self.update_ci.process_stack(job_list, self.stack['stack'],
                                              target_project)
        self.assertFalse(result)

    def test_orphan_search_no_target_project(self):
        result = self.update_ci.orphan_search_jenkins(
            jenkins_handle=None, stack=None, current_release='raring',
            target_project=None, orphan_release='quantal', remove=False)
        self.assertFalse(result)

    def test_orphan_search_with_one_orphan(self):
        self.jenkins_jobs = [
            {u'url': u'http://127.0.0.1:8080/job/autopilot-autolanding/',
             u'color': u'grey', u'name': u'autopilot-autolanding'},
            {u'url': u'http://127.0.0.1:8080/job/autopilot-ci/',
             u'color': u'grey', u'name': u'autopilot-ci'},
            {u'url': u'http://127.0.0.1:8080/job/autopilot-raring-amd64-ci/',
             u'color': u'grey', u'name': u'autopilot-raring-amd64-ci'},
            {u'url': u'http://127.0.0.1:8080/job/autopilot-quantal-amd64-ci/',
             u'color': u'grey', u'name': u'autopilot-quantal-amd64-ci'},
            {u'url': u'http://127.0.0.1:8080/job/libunity-raring-i386-ci/',
             u'color': u'grey', u'name': u'autopilot-raring-i386-ci'},
            {u'url': u'http://127.0.0.1:8080/job/autopilot-raring-armhf-autol'
             'anding/', u'color': u'grey', u'name': u'autopilot-raring-armhf'
             '-autolanding'}]
        self.jenkins_handle = Mock()
        mock_job_list = {'get_jobs.return_value': list(self.jenkins_jobs)}
        self.jenkins_handle.configure_mock(**mock_job_list)
        current_string = 'raring'
        orphan_string = 'quantal'
        target_project = 'autopilot'
        remove = True

        self.update_ci.orphan_search_jenkins(
            self.jenkins_handle, self.stack['stack'], current_string,
            target_project, orphan_string, remove)
        self.assertEqual(self.jenkins_handle.delete_job.call_count, 1)

    def test_orphan_search_without_orphan(self):
        self.jenkins_jobs = [
            {u'url': u'http://127.0.0.1:8080/job/autopilot-autolanding/',
             u'color': u'grey', u'name': u'autopilot-autolanding'},
            {u'url': u'http://127.0.0.1:8080/job/autopilot-ci/',
             u'color': u'grey', u'name': u'autopilot-ci'},
            {u'url': u'http://127.0.0.1:8080/job/autopilot-raring-amd64-ci/',
             u'color': u'grey', u'name': u'autopilot-raring-amd64-ci'},
            {u'url': u'http://127.0.0.1:8080/job/libunity-raring-i386-ci/',
             u'color': u'grey', u'name': u'autopilot-raring-i386-ci'},
            {u'url': u'http://127.0.0.1:8080/job/autopilot-raring-armhf-autol'
             'anding/', u'color': u'grey', u'name': u'autopilot-raring-armhf-'
             'autolanding'}]
        self.jenkins_handle = Mock()
        mock_job_list = {'get_jobs.return_value': list(self.jenkins_jobs)}
        self.jenkins_handle.configure_mock(**mock_job_list)
        current_string = 'raring'
        orphan_string = 'quantal'
        target_project = 'autopilot'
        remove = True

        self.update_ci.orphan_search_jenkins(
            self.jenkins_handle, self.stack['stack'], current_string,
            target_project, orphan_string, remove)
        self.assertEqual(self.jenkins_handle.delete_job.call_count, 0)
