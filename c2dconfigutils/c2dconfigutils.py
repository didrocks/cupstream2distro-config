import logging
import jenkins
import jinja2
import os
import urllib2
import yaml


def dict_union(result_dict, other_dict):
    if other_dict is None:
        return
    for key, val in other_dict.iteritems():
        if not isinstance(val, dict):
            result_dict[key] = val
        else:
            subdict = result_dict.setdefault(key, {})
            dict_union(subdict, val)


def unapproved_prerequisite_exists(mp):
    """check if there is an unapproved branch for a given merge proposal """
    prereq = mp.prerequisite_branch
    target_branch = mp.target_branch
    if prereq:
        #x is a merge-proposal object
        merges = [x for x in prereq.landing_targets
                  if x.target_branch.web_link == target_branch.web_link and
                  x.queue_status != u'Superseded']
        if len(merges) == 0:
            return True
        else:
            for merge in merges:
                #lets make our life simpler here and lets assume
                #all the MP needs to be merged even though in reality
                #their target branch might differ
                if merge.queue_status != u'Merged':
                    return True
    return False


def load_jenkins_credentials(path, jenkins_name):
    """ Load Credentials from credentials configuration file """
    if not os.path.exists(path):
        return False

    logging.debug('Loading credentials from %s', path)
    cred = yaml.safe_load(file(path, 'r'))
    return False if not jenkins_name in cred else cred[jenkins_name]


def load_default_cfg(basedir):
    """ Load default stack configuration from the defaults.conf file"""
    config_file = os.path.join(basedir, "config", "defaults.conf")
    if not os.path.isfile(config_file):
        return False

    logging.debug('Loading default stack configuration from %s', config_file)
    cfg = yaml.safe_load(file(config_file, 'r'))
    return False if not cfg else cfg


def load_stack_cfg(path, default_config):
    """ Load stack configuration from file, extending default_config

    TODO: Verify that mandatory settings are defined
    """

    if not os.path.exists(path):
        return False

    logging.debug('Loading stack configuration from %s', path)
    cfg = yaml.safe_load(file(path, 'r'))
    if not 'stack' in cfg:
        return False

    dict_union(default_config, cfg)
    return default_config['stack']


def get_jinja_environment(default_config_path, stack):
    if not 'tmpldir' in stack:
        tmpldir = os.path.join(default_config_path, 'jenkins-templates')
    else:
        tmpldir = stack['tmpldir']

    tmpldir = os.path.abspath(tmpldir)
    logging.debug('Templates directory: %s', tmpldir)

    if not os.path.exists(tmpldir):
        logging.error('Template directory doesn\'t exist')
        return False

    return jinja2.Environment(loader=jinja2.FileSystemLoader(tmpldir))


def get_jenkins_handle(jenkins_config):
    if not jenkins_config['url']:
        logging.error("Please provide a URL to the jenkins instance.")
        return False
    if 'username' in jenkins_config:
        jenkins_handle = jenkins.Jenkins(
            jenkins_config['url'],
            username=jenkins_config['username'],
            password=jenkins_config['password'])
    else:
        jenkins_handle = jenkins.Jenkins(jenkins_config['url'])
    return jenkins_handle


def setup_job(jenkins_handle, jjenv, jobname, tmplname, ctx, update=False):
    """ Generate template and create or update jenkins job

    :param jenkins_handle: jenkins handle
    :param jjenv: handle to jinja environment
    :param jobname: jenkins' job name
    :param tmplname: template name
    :param ctx: jinja context (dict) to merge with the template
    :param update: update existing job if True
    """
    logging.debug('Generating job: %s', jobname)
    tmpl = jjenv.get_template(tmplname)
    jkcfg = tmpl.render(ctx)
    jkcfg = jkcfg.replace(' \n', '')
    jkcfg = jkcfg.replace('>\n\n', '>\n')
    jobname = urllib2.quote(jobname)
    if not jenkins_handle.job_exists(jobname):
        logging.info("Creating Jenkins Job %s ", jobname)
        jenkins_handle.create_job(jobname, jkcfg)
    else:
        if update:
            logging.info("Reconfiguring Jenkins Job %s ", jobname)
            jenkins_handle.reconfig_job(jobname, jkcfg)
        else:
            logging.debug('update set to %s. Skipping reconfiguration of '
                          '%s', update, jobname)
    return True


def set_logging(debugmode=False):
    """Initialize logging"""
    logging.basicConfig(
        level=logging.DEBUG if debugmode else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s"
    )
    logging.debug('Debug mode enabled')
