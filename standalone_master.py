#!/usr/bin/env python
"""This script installs a local buildmaster"""
#https://wiki.mozilla.org/Release:Release_Automation_on_Mercurial:Staging_Specific_Notes
#https://wiki.mozilla.org/ReleaseEngineering/How_To/Setup_Personal_Development_Master#Create_a_build_master

# missing:
# ln -s ../buildbot-configs/mozilla/universal_master_sqlite.cfg master.cfg
import os
from lib.config import Config
from lib.master import Master, MasterError
from lib.shipit import Shipit, ShipitError
from lib.releaserunner import ReleaseRunner, ReleaseRunnerError
from lib.logger import logger
import argparse

if __name__ == '__main__':

    log = logger('staging release')

    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--cfg', help='configuration file', required=True)
    msg = 'username: if not specified, whoami will be used'
    parser.add_argument('-u', '--username', help=msg)
    args = parser.parse_args()

    # reading configuration
    config = Config()
    config.read_from(args.cfg)
    if args.username:
        config.set('common', 'username', args.username)
    log.debug(config)
    master = Master(config)
    try:
        master.install()
    except MasterError as error:
        log.error('unable to install buildbot master: {0}'.format(error))
