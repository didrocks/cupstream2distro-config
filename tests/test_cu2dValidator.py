from testscenarios import TestWithScenarios
from unittest import TestCase
from mock import patch, MagicMock

from c2dconfigutils.cu2dValidator import StacksValidator


class TestCheckDuplicateTargets(TestWithScenarios, TestCase):
    scenarios = [
        ('no_conflict',
         {
             'expected': False,
             'stacks': {
                 '../stacks/head/qa.cfg': {
                     'ci_default': {},
                     'projects': {'cupstream2distro-config': {}}
                 },
                 '../stacks/raring/qa.cfg': {
                     'ci_default': {},
                     'projects': {'cupstream2distro-config': {
                         'target_branch': 'lp:cupstream2distro-config/1.1'
                     }}}}}),
        ('conflict_in_different_stacks',
         {
             'expected': True,
             'stacks': {
                 '../stacks/head/qa.cfg': {
                     'ci_default': {},
                     'projects': {'cupstream2distro-config': {}}
                 },
                 '../stacks/raring/qa.cfg': {
                     'ci_default': {},
                     'projects': {'cupstream2distro-config': {
                         'target_branch': 'lp:cupstream2distro-config'}}
                 }
             }
         }),
        ('conflict_in_same_stack',
         {
             'expected': True,
             'stacks': {
                 '../stacks/head/qa.cfg': {
                     'ci_default': {},
                     'projects': {
                         'cupstream2distro-config': {},
                         'project2': {
                             'target_branch': 'lp:cupstream2distro-config'}
                     }
                 }
             }
         }),
        ('no_ci_default_conflict',
         {
             'expected': True,
             'stacks': {
                 '../stacks/head/qa.cfg': {
                     'projects': {'cupstream2distro-config': {}}
                 },
                 '../stacks/raring/qa.cfg': {
                     'ci_default': {},
                     'projects': {'cupstream2distro-config': {
                         'target_branch': 'lp:cupstream2distro-config'}}
                 }
             }
         }),
        ('no_projects',
         {
             'expected': False,
             'stacks': {
                 '../stacks/head/qa.cfg': {},
                 '../stacks/raring/qa.cfg': {
                     'ci_default': {},
                     'projects': {'cupstream2distro-config': {
                         'target_branch': 'lp:cupstream2distro-config'}}
                 }
             }
         }),
    ]

    def setUp(self):
        self.validator = StacksValidator()

    def test_check_duplicate_targets(self):
        self.assertEqual(self.expected,
                         self.validator.has_duplicate_targets(self.stacks))

    def test_call(self):
        validator = StacksValidator()
        validator.load_stacks = lambda x, y: self.stacks
        validator.parse_arguments = lambda: MagicMock()
        self.assertEqual(1 if self.expected else 0, validator(''))


class TestLoadStacks(TestCase):
    @patch('os.walk',
           new=MagicMock(return_value=[('../stacks/head', '', ('unity.cfg'))]))
    @patch('fnmatch.filter', new=lambda x, y: ['unity.cfg'])
    @patch('c2dconfigutils.cu2dValidator.load_stack_cfg')
    @patch('c2dconfigutils.cu2dValidator.load_default_cfg')
    def test_load_stacks(self, load_default_cfg, load_stack_cfg):
        load_default_cfg.return_value = {}
        load_stack_cfg.return_value = {'projects': {'unity': {
            'target_branch': 'lp:unity'}}}
        expected = {
            '../stacks/head/unity.cfg': load_stack_cfg.return_value
        }
        validator = StacksValidator()
        self.assertEqual(expected,
                         validator.load_stacks('', ''))

    def test_call_with_no_stacks(self):
        """call to the command must return 1 in case no stacks were loaded"""
        validator = StacksValidator()
        validator.load_stacks = lambda x, y: {}
        validator.parse_arguments = lambda: MagicMock()
        self.assertEqual(1, validator(''))

class TestCall(TestCase):
    def test_gibberish(self):
        sys_argv = ['./command', '-oheck']
        with patch('sys.argv', sys_argv):
            validator = StacksValidator()
            exception = False
            try:
                validator('')
            except SystemExit:
                exception = True
            self.assertTrue(exception)
