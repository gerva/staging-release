"""
download the list of locales
"""
import os
from tempfile import NamedTemporaryFile
from lib.download import download, DownloadError
from lib.logger import logger
log = logger(__name__)


class NoLocalesError(Exception):
    """
    I am really sorry but there are no locales for you
    """
    pass


def get_shipped_locales(locales_url):
    """ returns a tuple containing the list of shipped locales
        taken from locales_url
    """
    locales = []
    # need to set delete=False because otherwise this file
    # gets deleted just after the download as soon it gets closed
    temp_locales = NamedTemporaryFile(delete=False)
    try:
        download(locales_url, temp_locales.name)
    except DownloadError as error:
        log.error("Unable to get locales list")
        raise NoLocalesError(error)
    with open(temp_locales.name) as locales_file:
        for line in locales_file.readlines():
            line = line.strip()
            # removing empty lines and line = en-US
            if line and line != 'en-US':
                locales.append(line.strip())
    log.debug('locales: {0}'.format(locales))
    # removing temp file
    os.remove(temp_locales.name)
    return tuple(locales)
