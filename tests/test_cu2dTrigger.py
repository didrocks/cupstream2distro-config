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
             'expected_result': [ {'name': 'foo-autolanding',
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

    def test_process_stack(self):
        ret = self.jt.process_stack(self.stack)
        self.assertEqual(self.expected_result, ret)


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
        plugin_path = '/var/lib/jenkins/plugin'
        plugin = os.path.join(plugin_path, 'launchpadTrigger.py')
        calls = [
            call([plugin, '--branch=lp:foo', '--job=foo-ci', '--trigger-ci'],
                 cwd=plugin_path,
                 stderr=subprocess.STDOUT)]
        with patch('subprocess.check_call', check_call):
            self.jt.trigger_job(plugin_path, trigger)
            check_call.assert_has_calls(calls)

    def test_trigger_job_error(self):
        check_call = MagicMock()
        check_call.side_effect = subprocess.CalledProcessError(
            99, ['launchpadTrigger.py'])
        logging_error = MagicMock()
        trigger = {'name': 'foo-ci',
                   'branch': 'lp:foo',
                   'options': ['--trigger-ci']}
        plugin_path = '/var/lib/jenkins/plugin'
        with patch('subprocess.check_call', check_call):
            with patch("logging.error", logging_error):
                self.jt.trigger_job(plugin_path, trigger)
                logging_error.assert_called_once()
