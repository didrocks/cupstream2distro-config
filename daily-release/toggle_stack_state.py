#!/usr/bin/python
"""
Toggle job enabled state for a stack
"""
# Copyright (C) 2012, Canonical Ltd (http://www.canonical.com/)
#
# Author: Mathieu Trudel-Lapierre <mathieu@canonical.com>
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

import os
import logging
import yaml
import jenkins
import argparse
import xml.dom.minidom
import sys

PREFIX = 'cu2d'
DEFAULT_CREDENTIALS = os.path.expanduser('~/.cu2d.cred')
DEFAULT_RELEASE = 'head'

def run(jkcfg, stack, release, want_enabled, **kwargs):
    """ Force publication of a stack/release

    :param jkcfg: dictionary with the credentials
    :param stack: Name of the stack to publish
    :param release: Name of the release the stack belongs tostack to publish
    :param state: State to set to the job, True for enabled, False for disabled.
    """
    logging.debug('Logging to Jenkins')
    if 'username' in jkcfg:
        jkh = jenkins.Jenkins(jkcfg['url'],
                                  username=jkcfg['username'],
                                  password=jkcfg['password'])
    else:
        jkh = jenkins.Jenkins(jkcfg['url'])

    jobname = "cu2d-" + stack + "-" + release

    if not jkh.job_exists(jobname):
        logging.info("Job '%s' doesn't exists.", jobname)
        return False

    logging.info('Getting job state for %s', jobname)
    config = dom = xml.dom.minidom.parseString(jkh.get_job_config(jobname))
    jobdisabled = config.getElementsByTagName("disabled")[0].lastChild.data

    job_enabled = True
    if jobdisabled == "true":
        job_enabled = False

    if not job_enabled and want_enabled:
        logging.info('Enabling job: %s', jobname)
        jkh.enable_job(jobname)
    elif job_enabled and not want_enabled:
        logging.info('Disabling job: %s', jobname)
        jkh.disable_job(jobname)
    else:
        logging.info('Job is already in the %s state', "enabled" if job_enabled else "disabled")

    return True

def load_jenkins_credentials(path):
    """ Load Credentials from credentials configuration file """
    if not os.path.exists(path):
        return False

    logging.debug('Loading credentials from %s', path)
    cred = yaml.load(file(path, 'r'))

    for param in ('username', 'password', 'url', 'token'):
        if not param in cred['jenkins']:
            logging.error("Setting missing from jenkins credentials: %s. "
                          "Aborting!", param)
            sys.exit(1)
    return False if not 'jenkins' in cred else cred['jenkins']

def set_logging(debugmode=False):
    """Initialize logging"""
    logging.basicConfig(
        level=logging.DEBUG if debugmode else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s"
        )
    logging.debug('Debug mode enabled')

def main():
    parser = argparse.ArgumentParser(
        description='Toggle state for a stack.',
        formatter_class=argparse.RawTextHelpFormatter)


    parser.add_argument('-C', '--credentials', metavar='CREDENTIALFILE',
                        default=DEFAULT_CREDENTIALS,
                        help='use Jenkins and load credentials from '
                        'CREDENTIAL FILE (default: %s)' % DEFAULT_CREDENTIALS)
    parser.add_argument('-r', '--release',
                        default=DEFAULT_RELEASE,
                        help='Release the stack to publish belongs to '
                        '(default: %s)' % DEFAULT_RELEASE)
    parser.add_argument('-d', '--debug', action='store_true', default=False,
                        help='enable debug mode')
    parser.add_argument('--enable', action='store_true', default=False,
                        help='enable the stack')
    parser.add_argument('--disable', action='store_true', default=False,
                        help='disable the stack')
    parser.add_argument('stack', help='Name of the stack to publish')

    args = parser.parse_args()
    set_logging(args.debug)

    state = True # jobs enabled by default.
    if args.enable and args.disable:
	logging.error("Can't enable and disable at the same time. Choose one.")
	sys.exit(1)
    elif args.disable:
        state = False

    credentials = None
    if args.credentials:
        credentialsfile = args.credentials
        credentials = load_jenkins_credentials(
            os.path.expanduser(credentialsfile))
        if not credentials:
            logging.error('Credentials not found. Aborting!')
            sys.exit(1)

        if not run(credentials, args.stack, args.release, state):
            logging.error('Failed to run job. Aborting!')
            sys.exit(2)

if __name__ == "__main__":
    main()

