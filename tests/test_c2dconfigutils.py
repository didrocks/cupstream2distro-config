from testscenarios import TestWithScenarios
from c2dconfigutils.c2dconfigutils import (
    dict_union, unapproved_prerequisite_exists)
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
