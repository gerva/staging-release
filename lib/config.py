"""
this module manages the configuration
"""
import os
import pwd
import random
import string
import lib.ports as ports
from lib.which import which
import configparser

from lib.logger import logger
log = logger(__name__)


def get_username():
    """
    a replacement for whoami command
    """
    return pwd.getpwuid(os.getuid())[0]


def generate_random_password(size=8):
    """generates a random sequence of digit and upper case letter.
       size, controls password length.
    """
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for x in range(size))


class ConfigError(Exception):
    """Generic configuration error"""
    pass


class Config(configparser.ConfigParser):
    """this class manages the configuration"""
    def __init__(self):
        configparser.ConfigParser.__init__(
            self,
            interpolation=configparser.ExtendedInterpolation()
        )
        self.skip_validation = False

    def get(self, section, option, **_3to2kwargs):
        try:
            return super(Config, self).get(section, option, **_3to2kwargs)
        except Exception as error:
            log.debug(error)
            log.debug('requested section: {0}'.format(section))
            log.debug('requested option: {0}'.format(option))
            raise ConfigError(error)

    def get_list(self, section, option, **_3to2kwargs):
        """same as get() but returns a list instead of elements
           separated by ','
           It also removes new lines chars
        """
        values = self.get(section, option, **_3to2kwargs).split(',')
        # removing new and empty lines
        return [value.strip() for value in values if value]

    def set(self, section, option, value=None):
        try:
            super(Config, self).set(section, option, value)
        except (configparser.NoSectionError, TypeError) as error:
            log.debug(error)
            raise ConfigError(error)

    def read_from(self, filenames):
        """reads the configuration from a file or a list of files
           and then generates some runtime specific values
           as (ports, passwords,..)"""
        self.read(filenames)
        self._validate()
        self._set_runtime_values()

    def _validate(self):
        """validates a configuration.
           to skip the validation step, set self.skip_validation to True
        """
        if self.skip_validation:
            return

        for section in ('common', 'shipit', 'port_ranges', 'master'):
            if not self.has_section(section):
                msg = 'bad configuration file,'
                msg = '{0} missing section {1}'.format(msg, section)
                raise ConfigError(msg)

    def write_to(self, filename, sep='='):
        """this method writes interpolated values to a file.
           Standard write() creates a file with interpolated values
           left untouched.
           sep is the separator between option and value, it can be '=' or ':'
        """
        with open(filename, 'w') as dst:
            for section in self.sections():
                dst.write('[{0}]\n'.format(section))
                for option in self.options(section):
                    values = self.get(section, option)
                    values = values.split('\n')

                    if len(values) > 1:
                        # remove multiple \n
                        # option =
                        #    value
                        #    value
                        # generates:
                        # option =
                        #
                        #    value
                        #    value
                        line = '{0} {1}'.format(option, sep).strip()
                        line = '{0}\n'.format(line)
                        dst.write(line)
                        for value in values:
                            # multiple lines, they must be indented
                            # option =
                            #    value\n
                            #    value\n
                            #    value\n
                            dst.write('   {0}\n'.format(value))
                    else:
                        # single line
                        # write option = value\n
                        line = '{0} {1} {2}\n'.format(option, sep, values[0])
                        dst.write(line)

    def _set_runtime_values(self):
        """this method collects all the values that should be
            determined at runtime"""
        self._set_username()
        self._set_shipit_password()
        self._set_shipit_port()
        self._set_master_ports()
        self._set_python_path()

    def _set_username(self):
        # username cannot be hard coded in config.ini
        # it must be determined at run time
        # since username is a common option, let's have
        # it in the DEFAULT section so it will be available
        # in every section -- what about switching to python3 for
        # better interpolation?
        """sets the username
           assumption: your LDAP username is the same as your account
           on devmaster-01
        """
        username = get_username()
        log.debug('username: {0}'.format(username))
        self.set('common', 'username', username)

    def _set_shipit_password(self):
        """generates a random password for shipit"""
        # so there is no need to store a password in config.ini
        password = generate_random_password()
        log.debug('shipit password: {0}'.format(password))
        self.set('shipit', 'password', password)

    def _set_shipit_port(self):
        """finds an empty port for shipit"""
        shipit_port = self.get('shipit', 'port')
        if shipit_port:
            log.debug('shipit port: {0}'.format(shipit_port))
            return
        log.debug('shipit port is not defined, finding a random port.')
        port_range = int(self.get('port_ranges', 'range_size'))
        shipit_base_port = int(self.get('port_ranges', 'shipit'))
        _ports = ports.available_in_range(shipit_base_port,
                                          shipit_base_port + port_range)
        # random.sample(_ports, 1) returns a list
        shipit_port = str(random.sample(_ports, 1)[0])
        log.debug('shipit port: {0}'.format(shipit_port))
        self.set('shipit', 'port', shipit_port)

    def _set_master_ports(self):
        """finds three random ports for master (pb, ssh and http)"""
        # assuming that if http port is set, ssh and pb base ports are set too

        http_port = self.get('master', 'http_port')
        if http_port:
            log.debug("http port is set, ssh and pb base ports are set too")
            return
        # ports are not set so we need to pick up a random ports
        # this is the algorithm
        # (usually) http port is in range 8000-8999
        # ssh port == http_port - 1000
        # pb_port == http_poer + 1000
        port_range = int(self.get('port_ranges', 'range_size'))
        http_base_port = int(self.get('port_ranges', 'master_http'))
        ssh_base_port = int(self.get('port_ranges', 'master_ssh'))
        pb_base_port = int(self.get('port_ranges', 'master_pb'))
        _ports = ports.available_in_range(http_base_port,
                                          http_base_port + port_range)

        while True:
            if len(_ports) < 1:
                # no more ports to test
                break
            # sample returns a single element list
            http_port = random.sample(_ports, 1)[0]
            suffix = http_port - http_base_port
            # 8744 -> 744 (suffix)
            pb_port = pb_base_port + suffix
            ssh_port = ssh_base_port + suffix

            if not ports.in_use(pb_port) and not ports.in_use(ssh_port):
                # we have found 3 ports that fit into our algorithm!
                log.debug('master ports:')
                log.debug('http: {0}'.format(http_port))
                log.debug('ssh: {0}'.format(ssh_port))
                log.debug('pb: {0}'.format(pb_port))
                self.set('master', 'ssh_port', str(ssh_port))
                self.set('master', 'pb_port', str(pb_port))
                self.set('master', 'http_port', str(http_port))
                return
            # some of the ports was not free
            # discarding current port and picking up a new one
            _ports.discard(http_port)
        # giving up
        msg = "no available ports for your staging master. Giving up"
        raise ConfigError(msg)

    def _set_python_path(self):
        """adds the full path to your python executable in common:python_path"""
        self.set('common', 'python_path', which('python'))

    def __str__(self):
        msg = ""
        for section in self.sections():
            msg = "{0}[{1}]\n".format(msg, section)
            for option in self.options(section):
                msg = "{0}{1}={2}\n".format(msg, option,
                                            self.get(section, option))
        return msg
