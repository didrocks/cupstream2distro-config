from testscenarios import TestWithScenarios
from c2dconfigutils.c2dconfigutils import (
    dict_union, unapproved_prerequisite_exists, get_ci_base_job_name,
    disable_job, is_job_disabled, is_job_idle)
from testtools import TestCase
from testtools.matchers import Equals
from mock import MagicMock


class TestDictUnion(TestWithScenarios, TestCase):
    scenarios = [
        ('no_defaults',
         {
             'result_dict': {},
             'other_dict': {'stack': 'my stack'},
             'expected_result': {'stack': 'my stack'}}),
        ('all_empty',
         {
             'result_dict': {},
             'other_dict': {},
             'expected_result': {}}),
        ('override_default_fasttrack',
         {
             'result_dict': {'stack': {'projects': {
                 'compiz': {'fasttrack': True}}}},
             'other_dict': {'stack': {'projects': {
                 'compiz': {'fasttrack': False}}}},
             'expected_result': {'stack': {'projects': {
                 'compiz': {'fasttrack': False}}}}}),
        ('no_default_fasttrack',
         {
             'result_dict': {'stack': {'projects': {
                 'compiz': {}}}},
             'other_dict': {'stack': {'projects': {
                 'compiz': {'fasttrack': False}}}},
             'expected_result': {'stack': {'projects': {
                 'compiz': {'fasttrack': False}}}}}),

        ('default_fasttrack_for_unity',
         {
             'result_dict': {'stack': {'projects': {
                 'unity': {'fasttrack': True}}}},
             'other_dict': {'stack': {'projects': {
                 'compiz': {'fasttrack': False}}}},
             'expected_result': {'stack': {'projects': {
                 'compiz': {'fasttrack': False},
                 'unity': {'fasttrack': True}}}}}),
        ('lp1137400_only_default_config',
         {
             'result_dict': {'stack': {'projects': {
                 'compiz': {'fasttrack': True}}}},
             'other_dict': None,
             'expected_result': {'stack': {'projects': {
                 'compiz': {'fasttrack': True}}}}}),


    ]

    def test_dict_union(self):
        # Given/When
        dict_union(self.result_dict, self.other_dict)
        # Then
        self.assertThat(self.result_dict, Equals(self.expected_result))


class TestGetCiBaseJobName(TestWithScenarios, TestCase):
    scenarios = [
        ('no_target_branch',
         {'name': 'unity',
          'config': {},
          'expected_result': 'unity'}),
        ('target_branch_is_trunk',
         {'name': 'unity',
          'config': {'target_branch': 'lp:unity'},
          'expected_result': 'unity'}),
        ('project_name_different_than_trunk',
         {'name': 'compiz',
          'config': {'target_branch': 'lp:unity'},
          'expected_result': 'unity'}),
        ('target_branch_is_series_number',
         {'name': 'unity',
          'config': {'target_branch': 'lp:unity/7.0'},
          'expected_result': 'unity-7.0'}),
        ('target_branch_is_series_number_and_name_is_different',
         {'name': 'my_project',
          'config': {'target_branch': 'lp:unity/7.0'},
          'expected_result': 'unity-7.0'}),
        ('target_branch_is_series_name',
         {'name': 'unity',
          'config': {'target_branch': 'lp:unity/phablet'},
          'expected_result': 'unity-phablet'}),
        ('target_branch_is_in_team',
         {'name': 'unity',
          'config': {'target_branch': 'lp:~unity-team/unity/phablet'},
          'expected_result': 'unity-team-unity-phablet'}),
        ('target_branch_is_codename',
         {'name': 'codename',
          'config': {'target_branch': 'lp:~code-team/other_project/phablet'},
          'expected_result': 'code-team-other_project-phablet'}),
        ('target_branch_is_garbage',
         {'name': 'codename',
          'config': {'target_branch': '~code-team/other_project/phablet'},
          'expected_result': None}),
        ('libunity-phablet',
         {'name': 'libunity',
          'config': {'target_branch': 'lp:libunity/phablet'},
          'expected_result': 'libunity-phablet'}),
        ('lp-project',
         {'name': 'lplplp',
          'config': {'target_branch': 'lp:lplplp'},
          'expected_result': 'lplplp'}),

    ]

    def test_get_ci_base_job_name(self):
        # Given/When
        base_job_name = get_ci_base_job_name(self.name, self.config)
        # Then
        self.assertThat(base_job_name, Equals(self.expected_result))


class TestUnapprovedPrerequisiteExists(TestCase):

    def test_unapproved_prerequisite_no_prerequisite(self):
        mp = MagicMock()
        mp.prerequisite_branch = None
        self.assertFalse(unapproved_prerequisite_exists(mp))

    def test_unapproved_prerequisite_too_many_proposals(self):
        mp = MagicMock()
        mp.target_branch = MagicMock()
        mp.target_branch.web_link = 'url'
        prereq = MagicMock()
        prereq.landing_targets = [MagicMock(), MagicMock(), MagicMock()]
        for t in prereq.landing_targets:
                t.target_branch.web_link = 'url'
                t.queue_status = 'Approved'
        mp.prerequisite_branch = prereq
        self.assertTrue(unapproved_prerequisite_exists(mp))

    def test_unapproved_prerequisite_no_proposal_for_prerequisite(self):
        mp = MagicMock()
        prereq = MagicMock()
        prereq.landing_targets = []
        mp.prerequisite_branch = prereq
        self.assertTrue(unapproved_prerequisite_exists(mp))

    def test_unapproved_prerequisite_not_merged_yet(self):
        mp = MagicMock()
        mp.target_branch = MagicMock()
        mp.target_branch.web_link = 'url'
        prereq = MagicMock()
        prereq.landing_targets = [MagicMock()]
        for t in prereq.landing_targets:
                t.target_branch.web_link = 'url'
                t.queue_status = 'Approved'
        mp.prerequisite_branch = prereq
        self.assertTrue(unapproved_prerequisite_exists(mp))

    def test_unapproved_prerequisite_merged(self):
        mp = MagicMock()
        mp.target_branch = MagicMock()
        mp.target_branch.web_link = 'url'
        prereq = MagicMock()
        prereq.landing_targets = [MagicMock()]
        for t in prereq.landing_targets:
                t.target_branch.web_link = 'url'
                t.queue_status = 'Merged'
        mp.prerequisite_branch = prereq
        self.assertFalse(unapproved_prerequisite_exists(mp))


class TestDisableJob(TestCase):

    def test_disable_job(self):
        jenkins_handle = MagicMock()
        jenkins_handle.job_exists = MagicMock(return_value=True)
        disable_job(jenkins_handle, 'project-ci')
        jenkins_handle.disable_job.assert_called_once_with('project-ci')

    def test_disable_job_does_no_job(self):
        jenkins_handle = MagicMock()
        jenkins_handle.job_exists = MagicMock(return_value=False)
        disable_job(jenkins_handle, 'project-ci')
        self.assertEqual(jenkins_handle.disable_job.call_count, 0)


class TestIsJobDisabled(TestCase):

    def test_is_job_disabled(self):
        '''Verifies that a job is disabled if it is not buildable'''
        jenkins_handle = MagicMock()
        jenkins_handle.get_job_info = MagicMock(
            return_value={'buildable': False})
        ret = is_job_disabled(jenkins_handle, 'project-ci')
        self.assertTrue(ret)

    def test_is_job_enabled(self):
        '''Verifies that a job is not disabled if it is buildable'''
        jenkins_handle = MagicMock()
        jenkins_handle.get_job_info = MagicMock(
            return_value={'buildable': True})
        ret = is_job_disabled(jenkins_handle, 'project-ci')
        self.assertFalse(ret)

    def test_is_job_disabled_no_job(self):
        '''Verifies that a job that does not exist is disabled'''
        jenkins_handle = MagicMock()
        jenkins_handle.job_exists = MagicMock(return_value=False)
        jenkins_handle.get_job_info = MagicMock(
            return_value={'buildable': True})
        ret = is_job_disabled(jenkins_handle, 'project-ci')
        self.assertTrue(ret)


class TestIsJobIdle(TestCase):

    def test_is_job_idle(self):
        '''Verifies that a job is idle if lastBuild == lastCompletedBuild'''
        jenkins_handle = MagicMock()
        jenkins_handle.get_job_info = MagicMock(
            return_value={'lastBuild': 99,
                          'lastCompletedBuild': 99})
        ret = is_job_idle(jenkins_handle, 'project-ci')
        self.assertTrue(ret)

    def test_is_job_busy(self):
        '''Verifies that a job is idle if lastBuild == lastCompletedBuild'''
        jenkins_handle = MagicMock()
        jenkins_handle.get_job_info = MagicMock(
            return_value={'lastBuild': 99,
                          'lastCompletedBuild': 98})
        ret = is_job_idle(jenkins_handle, 'project-ci')
        self.assertFalse(ret)

    def test_is_job_idle_no_job(self):
        '''Verifies that a job that does not exist is idle'''
        jenkins_handle = MagicMock()
        jenkins_handle.job_exists = MagicMock(return_value=False)
        jenkins_handle.get_job_info = MagicMock(
            return_value={'lastBuild': 99,
                          'lastCompletedBuild': 98})
        ret = is_job_idle(jenkins_handle, 'project-ci')
        self.assertTrue(ret)
