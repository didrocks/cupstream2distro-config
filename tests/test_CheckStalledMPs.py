from mock import (patch, MagicMock)
from testtools import TestCase
from testtools.matchers import Equals, StartsWith

import datetime

from c2dconfigutils.cu2dWatchDog import CheckStalledMPs


class TestCheckBranch(TestCase):
    def setUp(self):
        super(TestCheckBranch, self).setUp()
        self.command = CheckStalledMPs()
        self.threshold = datetime.timedelta(minutes=1)

    def test_check_branch_no_lp_branch(self):
        branch = 'lp:branch'
        lp_branch = None
        launchpad = MagicMock()
        launchpad.branches.getByUrl = lambda url: lp_branch
        ret = self.command.check_branch(launchpad, branch, self.threshold)
        self.assertThat(ret, Equals(None))

    def test_check_branch_no_mps(self):
        branch = 'lp:branch'
        lp_branch = MagicMock()
        lp_branch.getMergeProposals = lambda: []
        launchpad = MagicMock()
        launchpad.branches.getByUrl = lambda url: lp_branch
        ret = self.command.check_branch(launchpad, branch, self.threshold)
        self.assertThat(ret, Equals([]))

    def test_check_branch_unapproved_mps(self):
        branch = 'lp:branch'
        lp_branch = MagicMock()
        lp_branch.getMergeProposals = lambda: [MagicMock()]
        launchpad = MagicMock()
        launchpad.branches.getByUrl = lambda url: lp_branch
        ret = self.command.check_branch(launchpad, branch, self.threshold)
        self.assertThat(ret, Equals([]))

    def _create_lp_objects(self, date_created):
        mp = MagicMock()
        mp.queue_status = 'Approved'
        mp.web_link = 'http://link'
        mp.date_reviewed = date_created
        lp_branch = MagicMock()
        lp_branch.getMergeProposals = lambda: [mp]
        launchpad = MagicMock()
        launchpad.branches.getByUrl = lambda url: lp_branch
        return launchpad

    def test_check_branch_mp_below_threshold(self):
        branch = 'lp:branch'
        unapproved_prerequisite_exists = lambda mp: False
        launchpad = self._create_lp_objects(datetime.datetime.now())
        with patch(
            'c2dconfigutils.cu2dWatchDog.unapproved_prerequisite_exists',
                unapproved_prerequisite_exists):
            ret = self.command.check_branch(launchpad, branch, self.threshold)
        self.assertThat(ret, Equals([]))

    def test_check_branch_mp_too_old(self):
        branch = 'lp:branch'
        unapproved_prerequisite_exists = lambda mp: False
        launchpad = self._create_lp_objects(
            datetime.datetime.now() - 2 * self.threshold)
        with patch(
            'c2dconfigutils.cu2dWatchDog.unapproved_prerequisite_exists',
                unapproved_prerequisite_exists):
            ret = self.command.check_branch(launchpad, branch, self.threshold)
        self.assertThat(ret[0], StartsWith('http://link was created '))

    def test_check_branch_mp_too_old_but_with_prerequisite(self):
        branch = 'lp:branch'
        unapproved_prerequisite_exists = lambda mp: True
        launchpad = self._create_lp_objects(
            datetime.datetime.now() - 2 * self.threshold)
        with patch(
            'c2dconfigutils.cu2dWatchDog.unapproved_prerequisite_exists',
                unapproved_prerequisite_exists):
            ret = self.command.check_branch(launchpad, branch, self.threshold)
        self.assertThat(ret, Equals([]))


class TestCheckStalledMps(TestCase):
    stack_cfg = {
        'projects': {
            'unity': {

            }
        }
    }

    transition_cfg = {
        'projects': {
            'unity': {}},
        'to_transition': {
            'compiz': {}},
    }

    no_projects_cfg = {
        'projects': None,
        'to_transition': {
            'compiz': {}},
    }

    def setUp(self):
        super(TestCheckStalledMps, self).setUp()
        self.command = CheckStalledMPs()
        self.launchpad_patch = patch('c2dconfigutils.cu2dWatchDog.Launchpad')
        self.launchpad_patch.start()
        self.load_default_cfg_patch = patch(
            'c2dconfigutils.cu2dWatchDog.load_default_cfg',
            lambda x: None)
        self.load_default_cfg_patch.start()

    def tearDown(self):
        super(TestCheckStalledMps, self).tearDown()
        self.launchpad_patch.stop()
        self.load_default_cfg_patch.stop()

    def test_process_stacks_no_stalled(self):
        load_stack_cfg = lambda x, y: self.stack_cfg
        self.command.check_branch = lambda x, y, z: []
        with patch('c2dconfigutils.cu2dWatchDog.load_stack_cfg',
                   load_stack_cfg):
            ret = self.command.process_stacks([1], 120, '')
            self.assertThat(ret, Equals(0))

    def test_process_stacks_with_transition(self):
        load_stack_cfg = lambda x, y: self.transition_cfg
        self.command.check_branch = MagicMock()
        with patch('c2dconfigutils.cu2dWatchDog.load_stack_cfg',
                   load_stack_cfg):
            self.command.process_stacks([1], 120, '')
            self.assertThat(self.command.check_branch.call_count,
                            Equals(1))

    def test_process_stacks_no_projects(self):
        load_stack_cfg = lambda x, y: self.no_projects_cfg
        self.command.check_branch = MagicMock()
        with patch('c2dconfigutils.cu2dWatchDog.load_stack_cfg',
                   load_stack_cfg):
            self.command.process_stacks([1], 120, '')
            self.assertThat(self.command.check_branch.call_count,
                            Equals(0))

    def test_process_stacks_one_stalled(self):
        load_stack_cfg = lambda x, y: self.stack_cfg
        self.command.check_branch = lambda x, y, z: ['stalled message']
        with patch('c2dconfigutils.cu2dWatchDog.load_stack_cfg',
                   load_stack_cfg):
            ret = self.command.process_stacks([1], 120, '')
            self.assertThat(ret, Equals(1))

    def test_process_stacks_no_lp_branch(self):
        '''Verify that if a branch is not found in lp, it is not stalled.'''
        load_stack_cfg = lambda x, y: self.stack_cfg
        self.command.check_branch = lambda x, y, z: None
        with patch('c2dconfigutils.cu2dWatchDog.load_stack_cfg',
                   load_stack_cfg):
            ret = self.command.process_stacks([1], 120, '')
            self.assertThat(ret, Equals(0))

    def test_process_stacks_stackcfg_fails_to_load(self):
        load_stack_cfg = lambda x, y: None
        with patch('c2dconfigutils.cu2dWatchDog.load_stack_cfg',
                   load_stack_cfg):
            ret = self.command.process_stacks([1], 120, '')
            self.assertThat(ret, Equals(0))
