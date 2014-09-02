import urllib2
from lib.logger import logger
log = logger(__name__)


class DownloadError(Exception):
    """Generic download error"""
    pass


def download(url, dst):
    """A simple file dowloader. Gets the content of url and writes it to dst"""
    request = urllib2.Request(url)
    try:
        log.debug('downloading {0} to {1}'.format(url, dst))
        response = urllib2.urlopen(request)
        # now write the response to dst
        with open(dst, 'wb') as dst_file:
            dst_file.write(response.read())
    except urllib2.HTTPError as error:
        log.error('Cannot download {0}, HTTP error: {1}'.format(url, error.code))
        raise DownloadError(error)
    except urllib2.URLError as error:
        log.error('Cannot download {0}, URL error: {1}'.format(url, error.reason))
        raise DownloadError(error)
