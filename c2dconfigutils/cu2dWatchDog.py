"""Check merge proposals that are approved but not merged for a longer period
of time.

"""
# Copyright (C) 2013, Canonical Ltd (http://www.canonical.com/)
#
# Author: Martin Mrazik <martin.mrazik@canonical.com>
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
import logging
import os
import datetime
from launchpadlib.launchpad import Launchpad


from c2dconfigutils import (
    load_default_cfg, load_stack_cfg, set_logging,
    unapproved_prerequisite_exists)

CREDENTIALS_FILE = os.path.expanduser(
    '/var/lib/jenkins/.launchpad.credentials')

LAUNCHPADLIB_DIR = os.path.expanduser('~/.launchpadlib-cu2d-check-stalled-mps')


class CheckStalledMPs(object):
    def parse_arguments(self):
        """ Parses the command line arguments

        return args: the parsed arguments
        """
        parser = argparse.ArgumentParser(
            description="Get all MP older than a given threshold")
        parser.add_argument('-t', '--threshold', required=True, type=int,
                            help="Threshold in minutes")
        parser.add_argument('-d', '--debug', action='store_true',
                            default=False, help='enable debug mode')
        parser.add_argument('stackcfg', nargs="+",
                            help='Path to a configuration file for the stack')
        return parser.parse_args()

    def check_branch(self, launchpad, branch, threshold):
        stalled = []
        logging.info('Looking at %s' % branch)
        lp_branch = launchpad.branches.getByUrl(url=branch)
        if not lp_branch:
            logging.error('%s not found' % branch)
            return
        mps = lp_branch.getMergeProposals()
        for mp in mps:
            if mp.queue_status == 'Approved':
                now = datetime.datetime.now(mp.date_reviewed.tzinfo)
                age = now - mp.date_reviewed
                if not unapproved_prerequisite_exists(mp) and age > threshold:
                    message = "%s was created %s ago!" % (mp.web_link, age)
                    logging.info(message)
                    stalled.append(message)
        return stalled

    def process_stacks(self, stacks, threshold, default_config_path):
        launchpad = Launchpad.login_with('check_stalled_mps', 'production',
                                         credentials_file=CREDENTIALS_FILE,
                                         launchpadlib_dir=LAUNCHPADLIB_DIR)
        threshold = datetime.timedelta(
            hours=threshold / 60,
            minutes=threshold % 60)
        stalled = []

        for stack in stacks:
            default_config = load_default_cfg(default_config_path)
            stackcfg = load_stack_cfg(stack, default_config)
            if not stackcfg:
                logging.error('Stack configuration failed to load. Ignoring')
            elif stackcfg['projects']:
                for project in stackcfg['projects']:
                    parameters = stackcfg['projects'][project]
                    target_branch = 'lp:' + project
                    if parameters and 'target_branch' in parameters:
                        target_branch = parameters['target_branch']
                    stalled = stalled + self.check_branch(launchpad,
                                                          target_branch,
                                                          threshold)
        for message in stalled:
            logging.error(message)
        if stalled:
            return 1
        return 0

    def __call__(self, default_config_path):
        """Entry point for cu2d-check-stalled-mps """
        args = self.parse_arguments()
        set_logging(args.debug)
        return self.process_stacks(args.stackcfg,
                                   args.threshold,
                                   default_config_path)
