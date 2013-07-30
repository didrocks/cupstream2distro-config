from mock import (patch, MagicMock, Mock)
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

class TestGetRebuildJob(TestWithScenarios, TestCase):
    stack = {'projects': {'compiz': None,
                          'nux': {'hook': 'my-hook',
                                  'ppa_target': 'ppa',
                                  'distributions': 'saucy'},
                          'unity': {
                              'target_branch': 'lp:unity/7.0'}}}
    scenarios = [
        ('empty_project',
         {
             'project_name': 'compiz',
             'expected': 'compiz-rebuild'}),
        ('unrelated_values',
         {
             'project_name': 'nux',
             'expected': 'nux-rebuild'}),
        ('has_target_branch',
         {
             'project_name': 'unity',
             'expected': 'unity-7.0-rebuild'}),
        ('not_a_project',
         {
             'project_name': 'other-project-rebuild',
             'expected': 'other-project-rebuild'})]

    def test_get_rebuild_job_name(self):
        update_ci = UpdateCi()
        actual = update_ci.get_rebuild_job(self.stack, self.project_name)
        self.assertEqual(self.expected, actual)


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
        config = {'hooks': 'my_hook',
                  'use_stack_ppa': True}
        job_data = {'stack_ppa': 'ppa_team/ppa_name'}
        expected = {'target_branch': 'lp:project',
                    'project_name': 'project',
                    'hooks': 'D09add_ppa~ppa_team~ppa_name my_hook',
                    'use_stack_ppa': True,
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

    def test_project_config_stack_false_use_stack_ppa(self):
        config = {'hooks': 'my_hook',
                  'use_stack_ppa': False}
        job_data = {'stack_ppa': 'ppa_team/ppa_name'}
        expected = {'target_branch': 'lp:project',
                    'project_name': 'project',
                    'hooks': 'my_hook',
                    'use_stack_ppa': False,
                    'parameter_list': [
                        JobParameter('hooks',
                                     'my_hook'),
                        JobParameter('target_branch',
                                     'lp:project'),
                        JobParameter('project_name',
                                     'project')]}
        actual = self.update_ci.process_project_config('project', config,
                                                       job_data)
        self.assertEqual(expected, actual)

    def test_project_config_stack_no_use_stack_ppa(self):
        config = {'hooks': 'my_hook'}
        job_data = {'stack_ppa': 'ppa_team/ppa_name'}
        expected = {'target_branch': 'lp:project',
                    'project_name': 'project',
                    'hooks': 'my_hook',
                    'parameter_list': [
                        JobParameter('hooks',
                                     'my_hook'),
                        JobParameter('target_branch',
                                     'lp:project'),
                        JobParameter('project_name',
                                     'project')]}
        actual = self.update_ci.process_project_config('project', config,
                                                       job_data)
        self.assertEqual(expected, actual)

    def test_project_config_stack_ppa_with_no_hooks(self):
        config = {'hooks': '',
                  'use_stack_ppa': True}
        job_data = {'stack_ppa': 'ppa_team/ppa_name'}
        expected = {'target_branch': 'lp:project',
                    'project_name': 'project',
                    'hooks': 'D09add_ppa~ppa_team~ppa_name',
                    'use_stack_ppa': True,
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
        config = {'hooks': False,
                  'use_stack_ppa': True}
        job_data = {'stack_ppa': 'ppa_team/ppa_name'}
        expected = {'target_branch': 'lp:project',
                    'project_name': 'project',
                    'hooks': 'D09add_ppa~ppa_team~ppa_name',
                    'use_stack_ppa': True,
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

    def test_project_config_parent_hooks(self):
        config = {'hooks': 'parent-hook'}
        expected = {'target_branch': 'lp:project',
                    'project_name': 'project',
                    'hooks': 'parent-hook',
                    'parameter_list': [
                        JobParameter('hooks',
                                     'parent-hook'),
                        JobParameter('target_branch',
                                     'lp:project'),
                        JobParameter('project_name',
                                     'project')]}
        actual = self.update_ci.process_project_config('project', config, {})
        self.assertEqual(expected, actual)

    def test_project_config_builder_hooks(self):
        config = {'hooks': 'builder-hook'}
        expected = {'target_branch': 'lp:project',
                    'project_name': 'project',
                    'hooks': 'builder-hook',
                    'builder_hooks': 'builder-hook',
                    'parameter_list': [
                        JobParameter('hooks',
                                     'builder-hook'),
                        JobParameter('target_branch',
                                     'lp:project'),
                        JobParameter('builder_hooks',
                                     'builder-hook'),
                        JobParameter('project_name',
                                     'project')]}
        actual = self.update_ci.process_project_config('project', config, {},
                                                       builder_job=True)
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

    def test_project_config_aggregate_tests_undefined(self):
        config = {'aggregate_tests': False}
        expected = {'target_branch': 'lp:project',
                    'project_name': 'project',
                    'parameter_list': [JobParameter('target_branch',
                                                    'lp:project'),
                                       JobParameter('project_name',
                                                    'project')]}
        self.update_ci._get_build_script = self._get_build_script_mock
        actual = self.update_ci.process_project_config('project', config, {})
        self.assertEqual(expected, actual)


class TestGenerateJobs(TestCase):
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
        self.update_ci.generate_jobs(job_list, 'foo', 'ci', 'ci', config,
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
        self.update_ci.generate_jobs(job_list, 'foo', 'ci', 'ci', config,
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
        self.update_ci.generate_jobs(job_list, 'foo', 'ci', 'ci', config,
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
        self.update_ci.generate_jobs(job_list, 'foo', 'ci', 'ci', config,
                                     self.job_template, self.build_template,
                                     {})
        actual = job_list[2]['ctx']['builder_list']
        self.assertEqual(expected, actual)

    def test_generate_rebuild_builder_list(self):
        config = {
            'configurations': {
                'raring-amd64': {'node_label': 'pbuilder'},
                'raring-i386': {'node_label': 'pbuilder'}}}
        expected = 'foo-raring-amd64-autolanding,foo-raring-i386-autolanding'
        job_list = []
        self.update_ci.generate_jobs(job_list, 'foo', 'rebuild', 'autolanding',
                                     config, self.job_template,
                                     self.build_template, {})
        actual = job_list[0]['ctx']['builder_list']
        self.assertEqual(expected, actual)

    def test_generate_rebuild_joblist(self):
        config = {
            'configurations': {
                'raring-amd64': {'node_label': 'pbuilder'},
                'raring-i386': {'node_label': 'pbuilder'}}}
        expected = 'foo-rebuild'
        job_list = []
        self.update_ci.generate_jobs(job_list, 'foo', 'rebuild', 'autolanding',
                                     config, self.job_template,
                                     self.build_template, {})
        actual = job_list[0]['name']
        self.assertEqual(expected, actual)
        self.assertEqual(1, len(job_list))


class TestUpdateJenkins(TestCase):
    def setUp(self):
        self.stack = {
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
        calls = [('autopilot-ci', 'template'),
                 ('xpathselect-ci', 'template'),
                 ('xpathselect-autolanding', 'template'),
                 ('autopilot-raring-amd64-autolanding', 'template'),
                 ('autopilot-raring-i386-autolanding', 'template'),
                 ('autopilot-autolanding', 'template')]
        sleep_mock = MagicMock()
        with patch('time.sleep', sleep_mock):
            self.update_ci.update_jenkins(self.jenkins, self.jjenv, self.stack)
        made_calls = []
        for c in self.jenkins.create_job.call_args_list:
            args, kwargs = c
            made_calls.append(args)
        self.assertEqual(made_calls, calls)

    def test_wait_list(self):
        self.update_ci.deploy_jobs = MagicMock(
            side_effect=[['autopilot-ci'], []])
        sleep_mock = MagicMock()
        with patch('time.sleep', sleep_mock):
            self.update_ci.update_jenkins(self.jenkins, self.jjenv, self.stack)
        sleep_mock.assert_called_with(10)


class TestAreChildrenDeployed(TestCase):

    def setUp(self):
        self.job_list = [{'name': 'project-ci',
                          'parents': None,
                          'deployed': False},
                         {'name': 'project-ci-builder',
                          'parents': ['project-ci'],
                          'deployed': False}]
        self.update_ci = UpdateCi()

    def test_children_not_deployed(self):
        ret = self.update_ci.are_children_deployed(self.job_list,
                                                   'project-ci')
        self.assertFalse(ret)

    def test_children_are_deployed(self):
        self.job_list[1]['deployed'] = True
        ret = self.update_ci.are_children_deployed(self.job_list,
                                                   'project-ci')
        self.assertTrue(ret)


class TestAreJobsIdle(TestCase):

    def setUp(self):
        self.job_list = ['project-rebuild', 'project-autolanding']
        self.expected_calls = [(None, 'project-rebuild'),
                               (None, 'project-autolanding')]
        self.update_ci = UpdateCi()

    def test_job_is_not_idle(self):
        """Verifies False when no jobs are idle"""
        is_job_idle = MagicMock(return_value=False)
        ret = True
        with patch('c2dconfigutils.cu2dUpdateCi.is_job_idle', is_job_idle):
            ret = self.update_ci.are_jobs_idle(None, self.job_list)
        self.assertFalse(ret)
        is_job_idle.assert_called_with(None, 'project-rebuild')

    def test_job_is_idle(self):
        """Verifies True when all jobs are idle"""
        is_job_idle = MagicMock(return_value=True)
        ret = False
        with patch('c2dconfigutils.cu2dUpdateCi.is_job_idle', is_job_idle):
            ret = self.update_ci.are_jobs_idle(None, self.job_list)
        self.assertTrue(ret)
        mock_calls = []
        for is_job_idle_call in is_job_idle.call_args_list:
            args, kwargs = is_job_idle_call
            mock_calls.append(args)
        self.assertEqual(mock_calls, self.expected_calls)

    def test_job_is_idle_and_not_idle(self):
        """Verifies False when at least one job is not idle"""
        is_job_idle = MagicMock(side_effect=[True, False])
        ret = True
        with patch('c2dconfigutils.cu2dUpdateCi.is_job_idle', is_job_idle):
            ret = self.update_ci.are_jobs_idle(None, self.job_list)
        self.assertFalse(ret)
        mock_calls = []
        for is_job_idle_call in is_job_idle.call_args_list:
            args, kwargs = is_job_idle_call
            mock_calls.append(args)
        self.assertEqual(mock_calls, self.expected_calls)


class TestDeployJobs(TestCase):

    def setUp(self):
        self.job_list = [{'name': 'project-ci',
                          'parents': None,
                          'template': 'template',
                          'ctx': 'ctx',
                          'deployed': False},
                         {'name': 'project-ci-builder',
                          'parents': 'project-ci',
                          'template': 'template',
                          'ctx': 'ctx',
                          'deployed': False},
                         {'name': 'project-autolanding',
                          'parents': None,
                          'template': 'template',
                          'ctx': 'ctx',
                          'deployed': False},
                         {'name': 'project-rebuild',
                          'parents': None,
                          'template': 'template',
                          'ctx': 'ctx',
                          'deployed': False},
                         {'name': 'project-autolanding-builder',
                          'parents': ['project-autolanding',
                                      'project-rebuild'],
                          'template': 'template',
                          'ctx': 'ctx',
                          'deployed': False}]
        self.update_ci = UpdateCi()
        self.setup_job = MagicMock()
        self.jenkins_handle = MagicMock()
        self.jenkins_handle.get_queue_info = MagicMock(return_value=[])
        self.is_job_disabled = MagicMock(return_value=True)
        self.is_job_idle = MagicMock(return_value=True)

    def test_deploy_jobs_first_iteration(self):
        '''Verifies that only child jobs are deployed on the first iteration'''
        expected = ['project-ci', 'project-autolanding', 'project-rebuild']
        actual = []
        with patch('c2dconfigutils.cu2dUpdateCi.is_job_disabled',
                   self.is_job_disabled), \
                patch('c2dconfigutils.cu2dUpdateCi.is_job_idle',
                      self.is_job_idle), \
                patch('c2dconfigutils.cu2dUpdateCi.setup_job',
                      self.setup_job):
            actual = self.update_ci.deploy_jobs(self.jenkins_handle, None,
                                                self.job_list)
        self.assertFalse(self.job_list[0]['deployed'])
        self.assertTrue(self.job_list[1]['deployed'])
        self.assertFalse(self.job_list[2]['deployed'])
        self.assertFalse(self.job_list[3]['deployed'])
        self.assertTrue(self.job_list[4]['deployed'])
        self.assertEqual(expected, actual)

    def test_deploy_jobs_final_iteration(self):
        '''Verifies that all jobs are deployed after the child jobs are
        deployed'''
        expected = []
        actual = []
        # Deploy the child jobs
        self.job_list[1]['deployed'] = True
        self.job_list[4]['deployed'] = True
        with patch('c2dconfigutils.cu2dUpdateCi.is_job_disabled',
                   self.is_job_disabled), \
                patch('c2dconfigutils.cu2dUpdateCi.is_job_idle',
                      self.is_job_idle), \
                patch('c2dconfigutils.cu2dUpdateCi.setup_job',
                      self.setup_job):
            actual = self.update_ci.deploy_jobs(self.jenkins_handle, None,
                                                self.job_list)
        self.assertTrue(self.job_list[0]['deployed'])
        self.assertTrue(self.job_list[1]['deployed'])
        self.assertTrue(self.job_list[2]['deployed'])
        self.assertTrue(self.job_list[3]['deployed'])
        self.assertTrue(self.job_list[4]['deployed'])
        self.assertEqual(expected, actual)

    def test_deploy_jobs_wait_list_all(self):
        '''Verifies that all jobs are wait listed if busy'''
        is_job_idle = MagicMock(return_value=False)
        expected = ['project-ci',
                    'project-autolanding',
                    'project-rebuild',
                    'project-ci-builder',
                    'project-autolanding-builder']
        actual = []
        with patch('c2dconfigutils.cu2dUpdateCi.is_job_disabled',
                   self.is_job_disabled), \
                patch('c2dconfigutils.cu2dUpdateCi.is_job_idle',
                      is_job_idle), \
                patch('c2dconfigutils.cu2dUpdateCi.setup_job',
                      self.setup_job):
            actual = self.update_ci.deploy_jobs(self.jenkins_handle, None,
                                                self.job_list)
        self.assertFalse(self.job_list[0]['deployed'])
        self.assertFalse(self.job_list[1]['deployed'])
        self.assertFalse(self.job_list[2]['deployed'])
        self.assertFalse(self.job_list[3]['deployed'])
        self.assertFalse(self.job_list[4]['deployed'])
        self.assertEqual(expected, actual)

    def test_deploy_jobs_disable_active_job(self):
        '''Verifies that a job is disabled if it is enabled'''
        job_list = [{'name': 'project-ci',
                     'parents': None,
                     'template': 'template',
                     'ctx': 'ctx',
                     'deployed': False}]
        is_job_disabled = MagicMock(return_value=False)
        expected = []
        actual = []
        with patch('c2dconfigutils.cu2dUpdateCi.is_job_disabled',
                   is_job_disabled), \
                patch('c2dconfigutils.cu2dUpdateCi.is_job_idle',
                      self.is_job_idle), \
                patch('c2dconfigutils.cu2dUpdateCi.setup_job',
                      self.setup_job):
            actual = self.update_ci.deploy_jobs(self.jenkins_handle, None,
                                                job_list)
        self.assertTrue(job_list[0]['deployed'])
        self.jenkins_handle.disable_job.assert_called_with('project-ci')
        self.assertEqual(expected, actual)

    def test_deploy_jobs_parent_active_children_deployed(self):
        '''Verifies that a parent job is placed on the wait list when all of
        it's children have been deployed, but it is still busy'''
        is_job_idle = MagicMock(return_value=False)
        expected = ['project-ci', 'project-autolanding', 'project-rebuild']
        actual = []
        # Deploy the child jobs
        self.job_list[1]['deployed'] = True
        self.job_list[4]['deployed'] = True
        with patch('c2dconfigutils.cu2dUpdateCi.is_job_disabled',
                   self.is_job_disabled), \
                patch('c2dconfigutils.cu2dUpdateCi.is_job_idle',
                      is_job_idle), \
                patch('c2dconfigutils.cu2dUpdateCi.setup_job',
                      self.setup_job):
            actual = self.update_ci.deploy_jobs(self.jenkins_handle, None,
                                                self.job_list)
        self.assertFalse(self.job_list[0]['deployed'])
        self.assertFalse(self.job_list[2]['deployed'])
        self.assertFalse(self.job_list[3]['deployed'])
        self.assertEqual(expected, actual)


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
                    'rebuild_template': 'rebuild-config.xml.tmpl',
                    'team': 'Autopilot Team',
                    'contact_email': 'address@email',
                    'distributions': 'raring,quantal,precise',
                    'ppa_target': 'ppa:autopilot/ppa',
                    'hooks': 'parent-hook',
                    'rebuild': 'autopilot-qt , autopilot-gtk',
                    'autolanding': {
                        'postbuild_job': 'autopilot-docs-upload',
                        'archive_artifacts': '**/output/*deb',
                        'configurations': {
                            'raring-amd64': {
                                'hooks': 'builder-hook',
                                'priority': 10000},
                            'raring-i386': {
                                'template': 'autopilot-config.xml.tmpl',
                                'node_label': 'pbuilder'}}}},
                'autopilot-gtk': {
                    'rebuild_template': 'rebuild-config.xml.tmpl',
                    'target_branch': 'lp:autopilot-gtk/1.0'},
                'autopilot-qt': {
                    'rebuild_template': 'rebuild-config.xml.tmpl'},
                'xpathselect': {
                    'rebuild': 'autopilot,another-project-rebuild'}}}}

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
                              'autopilot-rebuild',
                              'autopilot-qt-raring-amd64-ci',
                              'autopilot-qt-raring-armhf-ci',
                              'autopilot-qt-ci',
                              'autopilot-qt-raring-amd64-autolanding',
                              'autopilot-qt-raring-armhf-autolanding',
                              'autopilot-qt-autolanding',
                              'autopilot-qt-rebuild',
                              'xpathselect-raring-amd64-ci',
                              'xpathselect-raring-armhf-ci',
                              'xpathselect-ci',
                              'xpathselect-raring-amd64-autolanding',
                              'xpathselect-raring-armhf-autolanding',
                              'xpathselect-autolanding',
                              'autopilot-gtk-1.0-raring-amd64-ci',
                              'autopilot-gtk-1.0-raring-armhf-ci',
                              'autopilot-gtk-1.0-ci',
                              'autopilot-gtk-1.0-raring-amd64-autolanding',
                              'autopilot-gtk-1.0-raring-armhf-autolanding',
                              'autopilot-gtk-1.0-autolanding',
                              'autopilot-gtk-1.0-rebuild']
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
                                  'rebuild-config.xml.tmpl',
                                  'pbuilder-config.xml.tmpl',
                                  'pbuilder-config.xml.tmpl',
                                  'ci-config.xml.tmpl',
                                  'pbuilder-config.xml.tmpl',
                                  'pbuilder-config.xml.tmpl',
                                  'autolanding-config.xml.tmpl',
                                  'rebuild-config.xml.tmpl',
                                  'pbuilder-config.xml.tmpl',
                                  'pbuilder-config.xml.tmpl',
                                  'ci-config.xml.tmpl',
                                  'pbuilder-config.xml.tmpl',
                                  'pbuilder-config.xml.tmpl',
                                  'autolanding-config.xml.tmpl',
                                  'pbuilder-config.xml.tmpl',
                                  'pbuilder-config.xml.tmpl',
                                  'ci-config.xml.tmpl',
                                  'pbuilder-config.xml.tmpl',
                                  'pbuilder-config.xml.tmpl',
                                  'autolanding-config.xml.tmpl',
                                  'rebuild-config.xml.tmpl']
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
            elif job['name'].endswith('rebuild'):
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
                            # Skip hooks as parent and child may differ
                            if p.name == 'hooks':
                                continue
                            self.assertIn(p, child_params)

    def test_parent_child_hooks(self):
        """Verifies that a child builder job has a unique hook parameter when
        hooks are specified for the builder job"""
        actual_name_list = [job['name'] for job in self.job_list]
        self.assertIn('autopilot-autolanding', actual_name_list)
        self.assertIn('autopilot-raring-amd64-autolanding', actual_name_list)
        self.assertIn('autopilot-raring-i386-autolanding', actual_name_list)
        count = 0
        for job in self.job_list:
            if job['name'] == 'autopilot-autolanding':
                self.assertEqual(job['ctx']['hooks'], 'parent-hook')
                count += 1
            if job['name'] == 'autopilot-raring-amd64-autolanding':
                self.assertEqual(job['ctx']['builder_hooks'], 'builder-hook')
                self.assertEqual(job['ctx']['hooks'], 'builder-hook')
                count += 1
            if job['name'] == 'autopilot-raring-i386-autolanding':
                self.assertEqual(job['ctx']['builder_hooks'], 'parent-hook')
                self.assertEqual(job['ctx']['hooks'], 'parent-hook')
                count += 1
        # Make sure no assertion groups were missed
        self.assertEqual(count, 3)

    def test_rebuild_list(self):
        count = 0
        for job in self.job_list:
            if job['name'] == 'xpathselect-autolanding':
                self.assertEqual(job['ctx']['rebuild'],
                                 'autopilot-rebuild,another-project-rebuild')
                count += 1
            if job['name'] == 'autopilot-autolanding':
                self.assertEqual(job['ctx']['rebuild'],
                                 'autopilot-qt-rebuild,'
                                 'autopilot-gtk-1.0-rebuild')
                count += 1
        # Make sure no assertion groups were missed
        self.assertEqual(count, 2)

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
                              'autopilot-autolanding',
                              'autopilot-rebuild']
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
