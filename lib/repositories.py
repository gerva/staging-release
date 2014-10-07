"""
This module manages the cloning mozilla hg repos into user repos.
Created user repositories are named after the original repository
adding -self.bug (tracking bug id from bugzilla) to already existing user
repositories are not deleted.
Please not that this module can be very dangerous
"""

import os
from sh import ssh, hg
from sh import ErrorReturnCode_1, ErrorReturnCode
from lib.locales import get_shipped_locales, NoLocalesError
import shutil
import tempfile

from lib.logger import logger
log = logger(__name__)


class RepositoryError(Exception):
    """Generic Repository Eerror"""


class LocaleRepository(object):
    """manages locale repository"""
    def __init__(self, locale):
        self.locale = locale

    def _exec_ssh_cmd(self, cmd, ignore_exit_code_1=False):
        try:
            for line in ssh(cmd, _iter=True):
                log.debug(line.strip())
        except ErrorReturnCode_1:
            if ignore_exit_code_1:
                log.debug('ignoring exit code = 1')
            else:
                msg = 'error executing {0}'.format(' '.join(cmd))
                log.debug(msg)
                raise RepositoryError(msg)
        except ErrorReturnCode:
            log.debug(msg)
            raise RepositoryError(msg)

    def delete(self):
        locale = self.locale
        log.debug('deleting user repository {0}'.format(locale))
        cmd = ("hg.mozilla.org", "edit", locale,  "delete", "YES")
        log.debug('cmd: {0}'.format(' '.join(cmd)))
        try:
            self._exec_ssh_cmd(cmd, ignore_exit_code_1=True)
        except RepositoryError:
            log.debug('failed to delete user repository: {0}'.format(locale))

    def create(self):
        locale = self.locale
        log.debug('creating user repository {0}'.format(locale))
        cmd = ('hg.mozilla.org', 'clone',
               locale, 'l10n-central/{0}'.format(locale))
        log.debug('cmd: {0}'.format(' '.join(cmd)))
        try:
            self._exec_ssh_cmd(cmd)
        except RepositoryError:
            log.debug('failed to clone {0}'.format(locale))


class Repository(object):
    """Clones hg.m.o repositories into user's one
       manages checkouts and user's repository deletion
    """
    def __init__(self, configuration, name):
        self.configuration = configuration
        self.name = name
        self.bug = configuration.get('common', 'tracking_bug')
        self.local_checkout_dir = None

    def create_repo(self):
        """creates a reposiory as
           a copy of https://hg.mozilla.org/build/self.name/
           It creates hg.m.o/users/<ldap>_mozilla.com/self.name-<bug>
           appending -<bug> because this script creates and destroys that
           repo without asking for user permission.

        """
        conf = self.configuration
        src_repo_name = conf.get(self.name, 'src_repo_name')
        dst_repo_name = conf.get(self.name, 'dst_repo_name')
#        if not dst_repo_name.endswith(self.bug):
#            msg = "cowardly refusing to clone {0}".format(dst_repo_name)
#            msg = "{0}, its name does not end with {1}".format(msg, self.bug)
#            log.error(msg)
#            raise RepositoryError(msg)
        # added more robust check on pushing rather than cloning...

        cmd = ('hg.mozilla.org', 'clone', dst_repo_name,  src_repo_name)
        log.info('cloning {0} to {1}'.format(src_repo_name, dst_repo_name))
        log.debug('running ssh {0}'.format(' '.join(cmd)))
        ssh(cmd)

    def delete_user_repo(self, i_am_brave=False):
        """delete user's remote repository"""
        conf = self.configuration
        dst_repo_name = conf.get(self.name, 'dst_repo_name')
        if not dst_repo_name.endswith(self.bug) and not i_am_brave:
            msg = "cowardly refusing to delete {0}".format(dst_repo_name)
            msg = "{0}, its name does not end with {1}".format(msg, self.bug)
            log.error(msg)
            raise RepositoryError(msg)
        cmd = ("hg.mozilla.org", "edit", dst_repo_name,  "delete", "YES")
        log.info('deleting {0}'.format(dst_repo_name))
        log.debug('running ssh {0}'.format(' '.join(cmd)))
        output = []
        try:
            for line in ssh(cmd, _iter=True):
                out = line.strip()
                log.debug(out)
                output.append(out)
        except ErrorReturnCode_1:
            log.debug('trying to delete a non existing repo... pass')
        except ErrorReturnCode:
            msg = 'bad exit code executing {0}'.format(' '.join(cmd))
            log.error(msg)
            raise RepositoryError(msg)

    def clone_locally(self, dst_dir, branch='default', clone_from='user'):
        """clones the repo into dst_dir"""
        conf = self.configuration
        repo = conf.get(self.name, 'mozilla_repo')
        if clone_from != 'mozilla':
            repo = conf.get(self.name, 'user_repo')
        cmd = ('clone', repo, dst_dir)
        log.debug('running sh {0}'.format(' '.join(cmd)))
        self.local_checkout_dir = dst_dir
        hg_cmd = ('clone', '-b', branch, repo, dst_dir)
        try:
            for line in hg(hg_cmd, _iter=True):
                log.debug(line.strip())
        except ErrorReturnCode as error:
            msg = 'clone failed'
            msg = '{0}: hg {1}'.format(msg, ' '.join(cmd))
            msg = '{0} - error: {1}'.format(msg, error)
            log.debug(msg)
            raise RepositoryError('clone failed')

    def commit(self, commit_message):
        """commit local changes"""
        try:
            cmd = ('commit', '-m', commit_message)
            for line in hg(cmd, _cwd=self.local_checkout_dir):
                log.debug(line.strip())
        except ErrorReturnCode as error:
            msg = 'commit failed: {0}'.format(error)
            raise RepositoryError(msg)

    def _update_hgrc(self):
        """adds defaut-push in .hgrc"""
        hg_rc = os.path.join(self.local_checkout_dir, '.hg', 'hgrc')
        import configparser
        hgrc = configparser.ConfigParser()
        hgrc.read(hg_rc)
        default = str(hgrc.get('paths', 'default'))
        log.debug('default: {0}'.format(default))
        # DO NOT PUSH TO hg.m.o/build/<repo>
        if 'users' not in default:
            msg = 'cowardly refusing to push to a non user repo'
            msg = '{0} - (please use hg.m.o/users/<repo> instead)'.format(msg)
            raise RepositoryError(msg)
        # casting to str because pylint wants it
        # replace https or http with ssh
        default_push = default.replace('https:', 'ssh:')
        default_push = default_push.replace('http:', 'ssh:')
        log.debug('setting default-push to: {0}'.format(default_push))
        hgrc.set('paths', 'default-push', default_push)
        with open(hg_rc, 'wb') as configfile:
            hgrc.write(configfile)

        # log .hg/hgrc content
        with open(hg_rc, 'r') as configfile:
            for line in configfile:
                log.debug(line.strip())

    def push(self):
        """pushes local changes to the remote repository"""
        self._update_hgrc()
        try:
            # logging what is about to be pushed
            cmd = ('out', '-p', '--color', 'never')
            for line in hg(cmd, _cwd=self.local_checkout_dir):
                log.debug(line.strip())
            # and now log the push command
            for line in hg('push', _cwd=self.local_checkout_dir):
                log.debug(line.strip())
        except ErrorReturnCode as error:
            msg = 'push failed: {0}'.format(error)
            log.debug(msg)
            raise RepositoryError(msg)

    def tag(self, tag='default'):
        """tags a repository with tag, if tag is not provided,
           it will use tag_name function do determine the tag"""
        conf = self.configuration
        if tag == 'default':
            products = conf.get_list('common', 'staging_release')
            version = conf.get('common', 'version')
            tag = tag_name(version, products)
        try:
            cmd = ('tag', '-f', tag)
            for line in hg(cmd, _cwd=self.local_checkout_dir):
                log.debug(line.strip())
        except ErrorReturnCode as error:
            msg = 'tag failed: {0}'.format(error)
            log.debug(msg)
            raise RepositoryError(msg)


class Repositories(object):
    """Manages repositories in configuration"""
    def __init__(self, configuration):
        self.configuration = configuration

    def prepare_user_repos(self):
        """runs delete, create, clone and tag on every repository"""
        conf = self.configuration
        repos = conf.options('repositories')
        for repo in repos:
            am_i_brave = False
            log.info(repo)
            repo = Repository(conf, repo)
            if repo.name in ('mozilla-aurora', 'mozilla-beta'):
                # users release repos do not end with tracking bug number
                am_i_brave = True
            repo.delete_user_repo(i_am_brave=am_i_brave)
            repo.create_repo()
            if 'mozilla' not in repo.name:
                # skip release repository
                dst_dir = tempfile.mkdtemp()
                repo.clone_locally(dst_dir, clone_from='user')
                repo.tag()
                repo.push()
                shutil.rmtree(dst_dir)
            else:
                log.info('skip tagging of: {0}'.format(repo.name))
        # locales
        log.info('cloning locales repositiories')
        locales_url = conf.get('locales', 'url')
        try:
            locales = get_shipped_locales(locales_url)
        except NoLocalesError as error:
            log.debug(error)
            raise NoLocalesError(error)
        log.info('creating locales repositories')
        log.debug('locales: {0}'.format(locales))
        for locale in locales:
            log.info('repository: {0}'.format(locale))
            # make it optional from configuration/command line
            loc = LocaleRepository(locale)
            loc.delete()
            loc.create()

    def delete_all_repos(self):
        """runs delete, create, clone and tag on every repository"""
        conf = self.configuration
        repos = conf.options('repositories')
        for repo in repos:
            am_i_brave = False
            log.info(repo)
            repo = Repository(conf, repo)
            if repo.name in ('mozilla-aurora', 'mozilla-beta'):
                # users release repos do not end with tracking bug number
                am_i_brave = True
            repo.delete_user_repo(i_am_brave=am_i_brave)
#        # locales
#        log.info('cloning locales repositiories')
#        locales_url = conf.get('locales', 'url')
#        try:
#            locales = get_shipped_locales(locales_url)
#        except NoLocalesError as error:
#            log.debug(error)
#            raise NoLocalesError(error)
#        log.info('creating locales repositories')
#        log.debug('locales: {0}'.format(locales))
#        for locale in locales:
#            log.info('repository: {0}'.format(locale))
#             # make it optional from configuration/command line
#            loc = LocaleRepository(locale)
#            loc.delete()


def tag_name(version, products):
    """returns the tag name"""
    names = []
    version = version.replace('.', '_')
    for name in products:
        names.append('{0}_{1}_RELEASE'.format(name.upper(), version))
    return ', '.join(names)


def to_user_repo(repo_name, tracking_bug):
    """transforms mozilla's (build) repository to user's repo
        e.g. tools => tools-9999
    """
    return '{0}-{1}'.format(repo_name, tracking_bug)


def to_mozilla(repo_name, tracking_bug):
    """transforms user's repository name in mozilla repository names
        e.g. build/tools-9999 => tools
        e.g. h.m.o/build/tools-9999 => tools
    """
    bug = '-{0}'.format(tracking_bug)
    name = repo_name.split('/')[-1]
    if name.endswith(tracking_bug):
        name = name.partition(bug)[0]
    log.debug('canonical name: {0} => {1}'.format(repo_name, name))
    return name
