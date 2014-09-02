"""Updates user's repository configuration files"""

import os
import shutil
import tempfile
import time
from lib.logger import logger
from lib.repositories import Repository
from lib.download import download, DownloadError
from lib.master import generate_master_json
from lib.config import ConfigError
log = logger(__name__)


class PatchError(Exception):
    """Generic Patch error"""
    pass


class Patch(object):
    """
    Updates user's repositories so configuration points to the right location
    """
    def __init__(self, configuration, release_type, name):
        assert isinstance(release_type, (list, tuple))
        self.release_type = list(release_type)
        self.name = name
        # this property references a repo object
        self.repository = None
        self.tokens = None
        self.configuration = configuration
        self.dst_dir = None

    def clone(self, repository, branch):
        """clone repository locally"""
        self._create_temp_dir()
        log.debug('temporary directory: {0}'.format(self.dst_dir))
        repo = Repository(self.configuration, repository)
        log.info('cloning: {0}'.format(repository))
        # release runner reads from production branch and commits to default
        repo.clone_locally(self.dst_dir, branch=branch, clone_from='user')
        self.repository = repo

    def update_configs(self):
        """
        updates user repository to use just created repositories
        (rather than official mozilla ones)
        """
        files = self._files_to_update()
        conf = self.configuration
        username = conf.get('common', 'username')
        bug = conf.get('common', 'tracking_bug')
        repo_names = conf.get_list(self.name, 'replace')
        repos = patch_map(repo_names, username, bug)
        for repo in repos:
            # replace build/<repo> with users/... repo
            mozilla_repo, user_repo = repos[repo]
            for conf_in in files:
                # for every file...
                self._update_file(conf_in, mozilla_repo, user_repo)

    def _update_file(self, filename, src, dst):
        log.debug('patching: {0}'.format(filename))
        out = []
        with open(filename, 'r') as f_in:
            for line in f_in:
                if src in line:
                    if 'raw-file' not in line:
                        log.debug(line)
                        log.debug('{0} => {1}'.format(src, dst))
                        line = line.replace(src, dst)
                    log.debug(line)
                out.append(line)

        # write file before
        log.debug('writing changes to: {0}'.format(filename))
        with open(filename, 'w') as out_f:
            for line in out:
                out_f.write(line)

    def commit_changes(self):
        """executes hg commit on the local repository"""
        conf = self.configuration
        commit_msg = conf.get(self.name, 'commit_message')
        log.info('committing local changes')
        repo = self.repository
        repo.commit(commit_msg)
        repo.tag(tag='default')

    def _create_temp_dir(self):
        """creates a temporary directory"""
        self.dst_dir = tempfile.mkdtemp()
        log.debug('created temp dir: {0}'.format(self.dst_dir))

    def _delete_temp_dir(self):
        """removes temp directory"""
        log.debug('deleting temp dir: {0}'.format(self.dst_dir))
        try:
            shutil.rmtree(self.dst_dir)
        except OSError as error:
            # cannot delete temp dir
            log.debug('Patch: failed to delete temporary directory')
            log.debug(error)

    def push_changes(self):
        """push changes to remote and deletes temp repo"""
        log.info('pushing changes to remote')
        repo = self.repository
        repo.push()
        self._delete_temp_dir()

    def _files_to_update(self):
        """returns a list of files to update"""
        config = self.configuration
        files = self.release_type
        files.append('common_files')
        files.append('l10n')
        staging_files = []
        for element in files:
            config_files = config.get_list('staging_files', element)
            log.debug(config_files)
            staging_files.extend(config_files)
        # get the absolute path
        staging_files = [os.path.join(self.dst_dir, f) for f in staging_files]
        # remove not existing files
        staging_files = [f for f in staging_files if os.path.exists(f)]
        log.debug('files to be patched: {0}'.format(set(staging_files)))
        return set(staging_files)

    def _absoulute_path(self, filename):
        """returns the absolute path from the dst_dir"""
        try:
            return os.path.join(self.dst_dir, filename)
        except TypeError as error:
            log.debug(error)

    def _get_tokens(self):
        configuration = self.configuration
        try:
            self.tokens = configuration.get_list(self.name, 'tokens')
        except ConfigError:
            log.debug('{0} has no tokens'.format(self.name))
            self.tokens = []

    def fix(self):
        """patches, commits and pushes changes to the repository
           needs to be implemented in a sub-class
        """
        pass


class PatchBuildbotConfigs(Patch):
    """Fixes buildbot-configs"""
    def fix(self):
        """clones, updates, commit and pushes the your repo"""
        log.info('running {0}'.format(self.name))
        # sleep 20 sec
        time.sleep(20)
        for branch in ('default', 'production'):
            self.clone('buildbot-configs', branch)
            self.update_configs()
            self.commit_changes()
            # self.push_changes()
            time.sleep(20)


class PatchTools(Patch):
    """Fixes tools repository"""
    def fix(self):
        """creates production_master.json"""
        log.info('running {0}'.format(self.name))
        time.sleep(20)
        conf = self.configuration
        # production master
        pm_json_url = conf.get(self.name, 'src_production_masters_json')
        # get relative production-masters.json dst
        pm_json_dst = conf.get(self.name, 'dst_production_masters_json')
        log.info('*** pm_json_dst = {0}'.format(pm_json_dst))

        # clone the tools repository
        # tools has no 'production' branch...
        self.clone('tools', 'default')
        # we need to download src_production_masters_json in a temp file
        # because the file needs some detokenization (generate_master_json
        # does it)

        # now that we have a checkout dir,
        # update pm_json_dst with its absolute path
        pm_json_dst = os.path.join(self.dst_dir, pm_json_dst)
        log.info('*** pm_json_dst = {0}'.format(pm_json_dst))
        temp_pm_json = ''.join((pm_json_dst, 'temp'))
        # now download the production master template
        try:
            download(pm_json_url, temp_pm_json)
        except DownloadError as error:
            log.error('unable to download production master template')
            raise PatchError(error)

        # now we have a fresh copy production master json
        generate_master_json(self.configuration, temp_pm_json, pm_json_dst)
        # remove temp_pm_json
        os.remove(temp_pm_json)

        # commit the changes
        self.commit_changes()
        self.push_changes()


def patch_map(repository_names, username, tracking_bug):
    """Creates a map of the mozilla repo <-> user repo names"""
    my_map = {}
    # find a better way...
    # if a repository name in [repositories]
    # is commented out, it will not be patched
    for repo in repository_names:
        my_map[repo] = ('build/{0}'.format(repo),
                        'users/{0}_mozilla.com/{1}-{2}'.format(username,
                                                               repo,
                                                               tracking_bug))
    # replace stage-ffxbld -> username_mozilla.com
    my_map['stage-ffxbld'] = ('users/stage-ffxbld',
                              'users/{0}_mozilla.com'.format(username))
    for repo in ('mozilla-beta', 'mozilla-aurora', 'mozilla-esr31',):
        src = 'users/stage-ffxbld/'
        dst = 'users/{0}_mozilla.com/{1}'.format(username, repo)
        name = '{0}-stage'.format(repo)
        my_map[name] = (src, dst)

    # releases/mozilla-beta => users/<username>_mozilla.com/mozilla_beta
    src = 'releases/mozilla-beta'
    dst = 'users/{0}_mozilla.com/mozilla-beta'.format(username)
    my_map['mozilla-beta'] = (src, dst)

    return my_map
