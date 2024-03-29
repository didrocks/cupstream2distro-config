from mock import (call, patch, MagicMock)
import os
import subprocess
from testscenarios import TestWithScenarios
from unittest import TestCase

from c2dconfigutils.cu2dTrigger import JobTrigger


class TestGenerateTrigger(TestWithScenarios, TestCase):
    scenarios = [
        ('ci',
         {
             'project': 'foo',
             'job_type': 'ci',
             'config': {'target_branch': 'lp:foo'},
             'expected_result': {'name': 'foo-ci',
                                 'branch': 'lp:foo',
                                 'options': ['--trigger-ci']}}),
        ('autolanding',
         {
             'project': 'foo',
             'job_type': 'autolanding',
             'config': {'target_branch': 'lp:foo'},
             'expected_result': {'name': 'foo-autolanding',
                                 'branch': 'lp:foo',
                                 'options': ['--autoland']}}),
        ('autolanding-fasttrack',
         {
             'project': 'foo',
             'job_type': 'autolanding',
             'config': {'target_branch': 'lp:foo',
                        'fasttrack': True},
             'expected_result': {'name': 'foo-autolanding',
                                 'branch': 'lp:foo',
                                 'options': ['--autoland', '--fasttrack']}}),
    ]

    def setUp(self):
        self.jt = JobTrigger()

    def test_generate_trigger(self):
        ret = self.jt.generate_trigger(self.project, self.config,
                                       self.job_type)
        self.assertEqual(self.expected_result, ret)


class TestProcessStack(TestWithScenarios, TestCase):
    ci_default = {'ci_template': 'ci.xml.tmpl',
                  'autolanding_template': 'autolanding.xml.tmpl'}
    scenarios = [
        ('ci-and-autolanding',
         {
             'stack': {'ci_default': ci_default,
                       'projects': {'foo': {},
                                    'bar': {}}},
             'expected_result': [{'name': 'foo-ci',
                                  'branch': 'lp:foo',
                                  'options': ['--trigger-ci']},
                                 {'name': 'foo-autolanding',
                                  'branch': 'lp:foo',
                                  'options': ['--autoland']},
                                 {'name': 'bar-ci',
                                  'branch': 'lp:bar',
                                  'options': ['--trigger-ci']},
                                 {'name': 'bar-autolanding',
                                  'branch': 'lp:bar',
                                  'options': ['--autoland']}]}),
        ('projects-and-to_transition',
         {
             'stack': {'ci_default': ci_default,
                       'projects': {'foo': {}},
                       'to_transition': {'bar': {}}},
             'expected_result': [{'name': 'foo-ci',
                                  'branch': 'lp:foo',
                                  'options': ['--trigger-ci']},
                                 {'name': 'foo-autolanding',
                                  'branch': 'lp:foo',
                                  'options': ['--autoland']}]}),
        ('no-projects',
         {
             'stack': {'ci_default': ci_default,
                       'projects': None,
                       'to_transition': {'bar': {}}},
             'expected_result': []}),
        ('ci-only',
         {
             'stack': {'ci_default': ci_default,
                       'projects': {'foo': {'autolanding_template': None}}},
             'expected_result': [{'name': 'foo-ci',
                                  'branch': 'lp:foo',
                                  'options': ['--trigger-ci']}]}),
        ('autolanding-only',
         {
             'stack': {'ci_default': ci_default,
                       'projects': {'foo': {'ci_template': None}}},
             'expected_result': [{'name': 'foo-autolanding',
                                  'branch': 'lp:foo',
                                  'options': ['--autoland']}]}),
        ('none',
         {
             'stack': {'ci_default': ci_default,
                       'projects': {'foo': {'ci_template': None,
                                            'autolanding_template': None}}},
             'expected_result': []}),
    ]

    def setUp(self):
        self.jt = JobTrigger()
        self.trigger_types = ['ci', 'autolanding']

    def test_process_stack(self):
        ret = self.jt.process_stack(self.stack, self.trigger_types)
        self.assertEqual(self.expected_result, ret)


class TestGetLockName(TestWithScenarios, TestCase):
    scenarios = [
        ('head-unity',
         {'stack': '../head/unity.cfg',
          'expected': 'head-unity.cfg'}),
        ('experimental-unity',
         {'stack': '../experimental/unity.cfg',
          'expected': 'experimental-unity.cfg'}),
        ('absolute-path',
         {'stack': '/home/user/config/experimental/unity.cfg',
          'expected': 'experimental-unity.cfg'}),
        ('same-directory',
         {'stack': 'unity.cfg',
          'expected': 'unity.cfg'}),
        ('same-directory-explicit',
         {'stack': './unity.cfg',
          'expected': 'unity.cfg'}),
        ('relative-path',
         {'stack': 'experimental/unity.cfg',
          'expected': 'experimental-unity.cfg'}),
    ]

    def setUp(self):
        self.jt = JobTrigger()

    def test_get_lock_name(self):
        self.assertEqual(self.jt._get_lock_name(self.stack), self.expected)


class TestTriggerJob(TestWithScenarios, TestCase):
    ci_default = {'ci_template': 'ci.xml.tmpl',
                  'autolanding_template': 'autolanding.xml.tmpl'}
    stack = {'ci_default': ci_default,
             'projects': {'foo': {}}}

    def setUp(self):
        self.jt = JobTrigger()

    def test_trigger_job(self):
        check_call = MagicMock()
        trigger = {'name': 'foo-ci',
                   'branch': 'lp:foo',
                   'options': ['--trigger-ci']}
        plugin_path = '/iSCSI/jenkins/plugin'
        plugin = os.path.join(plugin_path, 'launchpadTrigger.py')
        calls = [
            call([plugin, '--lock-name=lock', '--branch=lp:foo',
                  '--job=foo-ci', '--trigger-ci'],
                 cwd=plugin_path,
                 stderr=subprocess.STDOUT)]
        with patch('subprocess.check_call', check_call):
            self.jt.trigger_job(plugin_path, trigger, 'lock')
            check_call.assert_has_calls(calls)

    def test_trigger_job_error(self):
        check_call = MagicMock()
        check_call.side_effect = subprocess.CalledProcessError(
            99, ['launchpadTrigger.py'])
        logging_error = MagicMock()
        trigger = {'name': 'foo-ci',
                   'branch': 'lp:foo',
                   'options': ['--trigger-ci']}
        plugin_path = '/iSCSI/jenkins/plugin'
        with patch('subprocess.check_call', check_call):
            with patch("logging.error", logging_error):
                self.jt.trigger_job(plugin_path, trigger, 'lock')
                logging_error.assert_called_once()


class TestTriggerStack(TestCase):
    def setUp(self):
        self.default_config = {}
        self.stack_cfg_name = 'stacks/head/foobar.cfg'
        self.plugin_path = '/tmp'
        self.stack_cfg = {'projects': {'foo': {},
                                       'bar': {}}}
        self.trigger_types = ['ci', 'autolanding']
        self.jt = JobTrigger()
        self.jt.process_stack = MagicMock(return_value=['trigger'])
        self.jt.trigger_job = MagicMock()

    @patch('c2dconfigutils.cu2dTrigger.load_stack_cfg')
    def test_trigger_stack(self, load_stack_cfg):
        """Verifiy jobs are triggered for a valid stack"""
        load_stack_cfg.return_value = self.stack_cfg
        ret = self.jt.trigger_stack(self.default_config, self.stack_cfg_name,
                                    self.plugin_path, self.trigger_types)
        load_stack_cfg.assert_called_with('stacks/head/foobar.cfg', {})
        self.jt.process_stack.assert_called_with(self.stack_cfg,
                                                 self.trigger_types)
        self.jt.trigger_job.assert_called_with(self.plugin_path, 'trigger',
                                               'head-foobar.cfg')
        self.assertEqual(ret, 0)

    @patch('c2dconfigutils.cu2dTrigger.load_stack_cfg')
    def test_trigger_stack_no_load(self, load_stack_cfg):
        """Verify no jobs are triggered when stack file fails to load"""
        load_stack_cfg.return_value = False
        ret = self.jt.trigger_stack(self.default_config, self.stack_cfg_name,
                                    self.plugin_path, self.trigger_types)
        load_stack_cfg.assert_called_with('stacks/head/foobar.cfg', {})
        self.assertFalse(self.jt.process_stack.called)
        self.assertFalse(self.jt.trigger_job.called)
        self.assertEqual(ret, 1)

    @patch('c2dconfigutils.cu2dTrigger.load_stack_cfg')
    def test_trigger_stack_no_project_section(self, load_stack_cfg):
        """Verify no jobs are triggered when no project section"""
        load_stack_cfg.return_value = {}
        ret = self.jt.trigger_stack(self.default_config, self.stack_cfg_name,
                                    self.plugin_path, self.trigger_types)
        load_stack_cfg.assert_called_with('stacks/head/foobar.cfg', {})
        self.assertFalse(self.jt.process_stack.called)
        self.assertFalse(self.jt.trigger_job.called)
        self.assertEqual(ret, 1)

    @patch('c2dconfigutils.cu2dTrigger.load_stack_cfg')
    def test_trigger_stack_no_projects(self, load_stack_cfg):
        """Verify no jobs are triggered when the project list is empty"""
        load_stack_cfg.return_value = {'projects': {},
                                       'to_transition': {'foo': {},
                                                         'bar': {}}}
        ret = self.jt.trigger_stack(self.default_config, self.stack_cfg_name,
                                    self.plugin_path, self.trigger_types)
        load_stack_cfg.assert_called_with('stacks/head/foobar.cfg', {})
        self.assertFalse(self.jt.process_stack.called)
        self.assertFalse(self.jt.trigger_job.called)
        self.assertEqual(ret, 0)

    @patch('c2dconfigutils.cu2dTrigger.load_stack_cfg')
    def test_trigger_stack_no_triggers(self, load_stack_cfg):
        """Verify no jobs are triggered when no triggers found"""
        load_stack_cfg.return_value = self.stack_cfg
        self.jt.process_stack = MagicMock(return_value=[])
        ret = self.jt.trigger_stack(self.default_config, self.stack_cfg_name,
                                    self.plugin_path, self.trigger_types)
        load_stack_cfg.assert_called_with('stacks/head/foobar.cfg', {})
        self.jt.process_stack.assert_called_with(self.stack_cfg,
                                                 self.trigger_types)
        self.assertFalse(self.jt.trigger_job.called)
        self.assertEqual(ret, 0)


class TestTriggerBranch(TestWithScenarios, TestCase):
    scenarios = [
        ('ci',
         {'trigger_type': ['ci'],
          'job_type': 'ci',
          'fasttrack': True,
          'options': ['--trigger-ci']}),
        ('autolanding-fasttrack',
         {'trigger_type': ['autolanding'],
          'job_type': 'autolanding',
          'fasttrack': True,
          'options': ['--autoland', '--fasttrack']}),
        ('autolanding-nofasttrack',
         {'trigger_type': ['autolanding'],
          'job_type': 'autolanding',
          'fasttrack': False,
          'options': ['--autoland']}),
    ]
    plugin_path = '/plugin_path'
    default_config = {}
    stackcfg_dir = '../stacks'
    target_branch = 'lp:branch'

    def test_trigger_project(self):
        """trigger_project must call self.trigger_job and return 0"""
        jt = JobTrigger()
        trigger = ['']
        jt.get_trigger_for_target = MagicMock(return_value=trigger)
        jt.trigger_job = MagicMock()
        ret = jt.trigger_project(self.plugin_path, self.default_config,
                                 self.target_branch, self.stackcfg_dir,
                                 self.trigger_type)
        jt.get_trigger_for_target.assert_called_once_with(
            self.default_config, self.target_branch,
            self.stackcfg_dir, self.job_type)
        jt.trigger_job.assert_called_once_with(self.plugin_path, trigger,
                                               lock_name='target-branch')
        self.assertEqual(ret, 0)

    def test_trigger_project_with_no_trigger(self):
        """trigger_project must return 1 if get_trigger_for_target doesn't
        return a trigger"""
        jt = JobTrigger()
        trigger = None
        jt.get_trigger_for_target = MagicMock(return_value=trigger)
        jt.trigger_job = MagicMock()
        ret = jt.trigger_project(self.plugin_path, self.default_config,
                                 self.target_branch, self.stackcfg_dir,
                                 self.trigger_type)
        self.assertEqual(ret, 1)
        jt.trigger_job.assert_has_calls([])

    @patch('os.walk',
           new=MagicMock(return_value=[('../stacks/head', '', ('unity.cfg'))]))
    @patch('fnmatch.filter', new=lambda x, y: ['unity.cfg'])
    @patch('c2dconfigutils.cu2dTrigger.load_stack_cfg')
    def test_get_trigger_for_target(self, load_stack_cfg):
        jt = JobTrigger()
        stackcfg = {
            'ci_default': {
                'fasttrack': self.fasttrack
            },
            'projects': {
                'branch': {
                    'hooks': 'D09some_hook'
                }
            }
        }
        load_stack_cfg.return_value = stackcfg
        trigger = jt.get_trigger_for_target(self.default_config,
                                            self.target_branch,
                                            self.stackcfg_dir,
                                            self.job_type)
        expected_trigger = {
            'name': 'branch-{}'.format(self.job_type),
            'branch': self.target_branch,
            'options': self.options
        }
        self.assertEqual(trigger, expected_trigger)

    @patch('os.walk',
           new=MagicMock(return_value=[('../stacks/head', '', ('unity.cfg'))]))
    @patch('fnmatch.filter', new=lambda x, y: [])
    def test_get_trigger_for_nonexisting_project(self):
        jt = JobTrigger()
        trigger = jt.get_trigger_for_target(self.default_config,
                                            self.target_branch,
                                            self.stackcfg_dir,
                                            self.trigger_type)
        self.assertEqual(trigger, None)


class TestCall(TestCase):
    def test_gibberish(self):
        sys_argv = ['./command', '-oheck']
        with patch('sys.argv', sys_argv):
            jt = JobTrigger()
            exception = False
            try:
                jt('')
            except SystemExit:
                exception = True
            self.assertTrue(exception)

    def test_noparams(self):
        sys_argv = ['./command']
        with patch('sys.argv', sys_argv):
            jt = JobTrigger()
            exception = False
            try:
                jt('')
            except SystemExit:
                exception = True
            self.assertTrue(exception)

    @patch('c2dconfigutils.cu2dTrigger.load_default_cfg')
    def test_stackcfg_defined(self, load_default_cfg):
        sys_argv = ['./command', '--trigger-ci', '../stacks/head/stack.cfg']
        with patch('sys.argv', sys_argv):
            jt = JobTrigger()
            jt.trigger_stack = MagicMock()
            jt('')
            jt.trigger_stack.assert_called_once()

    @patch('c2dconfigutils.cu2dTrigger.load_default_cfg')
    def test_trigger_ci_and_autolanding_stack(self, load_default_cfg):
        load_default_cfg.return_value = {}
        sys_argv = ['./command', '--trigger-ci', '--trigger-autolanding',
                    '../stacks/head/stack.cfg']
        with patch('sys.argv', sys_argv):
            jt = JobTrigger()
            jt.trigger_stack = MagicMock()
            jt('')
            jt.trigger_stack.assert_called_once_with(
                {}, '../stacks/head/stack.cfg',
                JobTrigger.DEFAULT_PLUGIN_PATH,
                ['autolanding', 'ci'])

    @patch('c2dconfigutils.cu2dTrigger.load_default_cfg')
    def test_missing_type(self, load_default_cfg):
        sys_argv = ['./command', '../stacks/head/stack.cfg']
        with patch('sys.argv', sys_argv):
            jt = JobTrigger()
            jt.trigger_stack = MagicMock()
            try:
                jt('')
            except SystemExit:
                exception = True
            self.assertTrue(exception)

    @patch('c2dconfigutils.cu2dTrigger.load_default_cfg')
    def test_trigger_autolanding(self, load_default_cfg):
        load_default_cfg.return_value = {}
        branch = 'lp:branch'
        plugin_path = '/plugin/path'
        cfg_dir = '../stacks'
        sys_argv = ['./command', '--trigger-autolanding',
                    '--branch', branch, '-p', plugin_path, '-D', cfg_dir]
        with patch('sys.argv', sys_argv):
            jt = JobTrigger()
            jt.trigger_project = MagicMock()
            jt('')
            jt.trigger_project.assert_called_once_with(plugin_path, {}, branch,
                                                       cfg_dir, ['autolanding'])

    @patch('c2dconfigutils.cu2dTrigger.load_default_cfg')
    def test_trigger_ci(self, load_default_cfg):
        load_default_cfg.return_value = {}
        branch = 'lp:branch'
        plugin_path = '/plugin/path'
        cfg_dir = '../stacks'
        sys_argv = ['./command', '--trigger-ci',
                    '--branch', branch, '-p', plugin_path, '-D', cfg_dir]
        with patch('sys.argv', sys_argv):
            jt = JobTrigger()
            jt.trigger_project = MagicMock()
            jt('')
            jt.trigger_project.assert_called_once_with(plugin_path, {}, branch,
                                                       cfg_dir, ['ci'])

    @patch('c2dconfigutils.cu2dTrigger.load_default_cfg')
    def test_trigger_ci_and_autolanding_branch(self, load_default_cfg):
        load_default_cfg.return_value = {}
        branch = 'lp:branch'
        plugin_path = '/plugin/path'
        cfg_dir = '../stacks'
        sys_argv = ['./command', '--trigger-ci', '--trigger-autolanding',
                    '--branch', branch, '-p', plugin_path, '-D', cfg_dir]
        with patch('sys.argv', sys_argv):
            jt = JobTrigger()
            jt.trigger_project = MagicMock()
            jt('')
            jt.trigger_project.assert_called_once_with(plugin_path, {}, branch,
                                                       cfg_dir,
                                                       ['autolanding', 'ci'])

    @patch('c2dconfigutils.cu2dTrigger.load_default_cfg')
    def test_trigger_ci_missing_branch(self, load_default_cfg):
        load_default_cfg.return_value = {}
        branch = 'lp:branch'
        plugin_path = '/plugin/path'
        cfg_dir = '../stacks'
        sys_argv = ['./command', '--trigger-ci',
                    '-p', plugin_path, '-D', cfg_dir]
        with patch('sys.argv', sys_argv):
            jt = JobTrigger()
            jt.trigger_project = MagicMock()
            try:
                jt('')
            except SystemExit:
                exception = True
            self.assertTrue(exception)
