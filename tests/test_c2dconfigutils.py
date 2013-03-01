from testscenarios import TestWithScenarios
from c2dconfigutils.c2dconfigutils import dict_union
from testtools import TestCase
from testtools.matchers import Equals


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
