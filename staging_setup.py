#!/usr/bin/env python

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
    parser.add_argument('-b', '--bug', help='bug tracking id', required=True)
    parser.add_argument('-v', '--version', help='version', required=True)
    msg = 'staging release comma separated values (e.g: firefox,fennec)'
    parser.add_argument('-r', '--release', help=msg, required=True)
    msg = 'username: if not specified, whoami will be used'
    parser.add_argument('-u', '--username', help=msg)
    args = parser.parse_args()

    # reading configuration
    config = Config()
    config_ini = os.path.join(os.path.dirname(__file__), "config.ini")
    config.read_from(args.cfg)
    config.set('common', 'tracking_bug', args.bug)
    config.set('common', 'staging_release', args.release)
    if args.username:
        config.set('common', 'username', args.username)
    log.debug(config)
    master = Master(config)
    shipit = Shipit(config)
    releaseR = ReleaseRunner(config)
    relese_type = config.get_list('common', 'staging_release')
    try:
        master.install()
        shipit.install()
        releaseR.install()
    except MasterError as error:
        log.error('unable to install buildbot master: {0}'.format(error))
    except ShipitError as error:
        log.error('unable to install shipit: {0}'.format(error))
    except ReleaseRunnerError as error:
        log.error('unable to install release runner: {0}'.format(error))
