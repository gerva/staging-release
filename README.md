staging-release
===============

This project goal is to automate all the procedures described in:
* [setup a personal development master] (https://wiki.mozilla.org/ReleaseEngineering/How_To/Setup_Personal_Development_Master#Create_a_build_master)
* [staging release specific notes] (https://wiki.mozilla.org/Release:Release_Automation_on_Mercurial:Staging_Specific_Notes)

This tools installs:

* buildbot master
* release runner
* [release-kickoff] (https://github.com/bhearsum/release-kickoff/)

It also takes care of creating the required users repositories (buildbot-configs, buildbotcustom, ...) and locales.

Assumptions
===========

* You already have created at least a user repository on hg.mozilla.org, more [here] (https://developer.mozilla.org/en-US/docs/Creating_Mercurial_User_Repositories)
* You know what you're doing.

install
=======
This is a python project, some external libraries are required, to install all the dependencies, run the following command in a [virtual environment](http://docs.python-guide.org/en/latest/dev/virtualenvs/)
```
pip install -r requirements/dev.txt
```

use
===
To run a staging release, we need to create some repositories and install the staging release stack.

Creating required user repositories
-----------------------------------
Disclaimer: this script may *destroy* some of your user repositories!

A staging release needs commit access to the following repositories:
* buildbotcustom
* buildbot-configs
* tools
* locales repos
* and many more

We don't want to mess up with official repositories so we the first step is to create some copies of the mozilla repositories and use them instead.
To create all the require repositories, run the following script:
```
python repos_setup.py --cfg config/configuration_ini_file \
                      --bug <tracking_bug_number> \
                      --release {firefox,fennec,thunderbird}
                      --username (optional) <your ldap username>

```

Parameters:
* cfg a configuration file, it holds all the information about the repository names
* username: your ldap username, if not provided, it will try to figure out your current username and use in instead.
* bug a tracking bug number: this script assumes that you already have some personal repositories already checked out in https://hg.mozilla.org/mozilla/users/__your user__/__repository name__ so it will try not to delete them (but it depends on how you wrote your configuration files)

How it works:
This script loads the configuration file specified in the --cfg option and looks for the [repository] section. For each repository name in this section, it clones the mozilla official repository into the user's repository.
Let's start with an example, suppose we have the following section into our configuration file (called example.ini):

```
[repositories]
buildbot-configs=

[buildbot-configs]
name=buildbot-configs
src_repo_name = build/buildbot-configs
dst_repo_name = buildbot-configs-00012345
mozilla_repo=https://hg.mozilla.org/build/buildbot-configs
user_repo=https://hg.mozilla.org/users/mgervasini_mozilla.com/buildbot-configs-00012345
```

... and we run the following command:
```
python repos_setup.py --cfg example.ini --bug 00012345 --release firefox --username mgervasini
```

The script will clone https://hg.mozilla.org/build/buildbot-configs to https://hg.mozilla.org/users/mgervasini_mozilla.com/buildbot-configs-00012345. A user has full read/write access to its repositories so, from now on, we will use our personal repository instead of Mozilla's one.

You can run this script as many times you want. Each run will delete anything from users/mgervasini_mozilla.com/buildbot-configs-00012345 and reclone it from 00012345://hg.mozilla.org/build/buildbot-configs. The tracking bug number is used for commit messages to, it can be a real bugizilla bug number or any string, it's main use is to avoid to delete anything important in YOUR repositories.

Please note: This is just an example, running it with a *real* configuration file will create a *lots* of repositories, don't forget to delete them when you are done with the release.

This script will also patch some configuration files so you don't have to manually update your master/release-runner.ini/... files to perform a staging release.



Installing the staging release stack
------------------------------------
docs coming soon


Installing a standalone master
------------------------------
docs coming soon

extend
======

* create a custom configuration

* create a new component

TODO
====

* create a test master

* create a staging master
