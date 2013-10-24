#!/usr/bin/env python
# 
# Example short urls to try:
# http://t.co/oZ2IWUfW9m - relatively sane - should end at gift-card-rewards.com
# - update: oops, disabled!
# http://bit.ly/1b5KFTr - 14 redirects! - should end at www.nextag.com
# http://bit.ly/1c9r7Bt - meta refresh - actually ends at www.toshiba.com
# - Careful, they can detect you re-using urls partway through
#   the chain (session ids) and give you a different redirect or a 500
# http://bit.ly/18bArwp - meta refresh - ends at accessories.us.dell.com
# - via zdbb.net, who might be responsible for the blocking of the last one
# http://bit.ly/1a9xteY - relative Location - ends at accessories.us.dell.com
# - and the location doesn't start with a /
import os
import re
import sys
import httplib
import urlparse
import subprocess
import HTMLParser
import distutils.spawn

script_name = os.path.basename(sys.argv[0])
USAGE = "USAGE: $ "+script_name+" http://long.url/stuff"
COLUMNS_DEFAULT = 80
SCHEME_REGEX = r'^[^?#:]+://'

USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:25.0) Gecko/20100101 Firefox/25.0'
ACCEPT = 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
ACCEPT_LANG = 'en-US,en;q=0.5'
ACCEPT_ENCOD = 'gzip, deflate'
CONNECTION = 'keep-alive'
# HEADERS = {'User-Agent':USER_AGENT, 'Accept':ACCEPT, 'Accept':ACCEPT,
#   'Accept-Language':ACCEPT_LANG, 'Accept-Encoding':ACCEPT_ENCOD,
#   'Connection':CONNECTION}
# Some of the headers in the full list can cause problems
HEADERS = {'User-Agent':USER_AGENT}

def main():
  if len(sys.argv) > 1:
    url = sys.argv[1]
  else:
    print USAGE
    exit()
  if url == '-h' or url == '--help':
    print USAGE
    exit()

  quiet = False
  if '-q' in sys.argv:
    quiet = True

  columns = get_columns(COLUMNS_DEFAULT)

  if not re.search(SCHEME_REGEX, url):
    url = 'http://'+url

  summary = ''
  redirects = 0
  done = False
  while not done:
    print url
    url_parsed = urlparse.urlsplit(url)
    scheme = url_parsed[0]
    domain = url_parsed[1]
    path = url_parsed[2]
    if not path:
      path = '/'

    query = url_parsed[3]
    if query:
      path += '?'+query

    if scheme == 'http':
      conex = httplib.HTTPConnection(domain)
    elif scheme == 'https':
      conex = httplib.HTTPSConnection(domain)
    else:
      fail("Error: Unrecognized URI scheme in:\n"+url)

    # Each of these steps can throw exceptions
    conex.request('GET', path, '', HEADERS)
    response = conex.getresponse()
    html = response.read()

    location_url = response.getheader('Location')

    if location_url is None:
      if response.status == 200:
        # html = response.read()
        meta_url = meta_redirect(html)
        if meta_url:
          url = meta_url
          summary += "meta refresh from  "+url[:columns-19]+"\n"
        else:
          done = True
      else:
        fail("Error: non-200 status and no Location header. Status message:\n\t"
          +str(response.status)+': '+response.reason)
    else:
      if not quiet and not re.search(SCHEME_REGEX, location_url):
        if location_url.startswith('/'):
          summary += "absolute path from "+url[:columns-19]+"\n"
        else:
          summary += "relative path from "+url[:columns-19]+"\n"
      url = urlparse.urljoin(url, location_url)

    conex.close()

    if not done:
      redirects+=1

  if not quiet:
    sys.stdout.write("\n"+summary)
    print "total redirects: "+str(redirects)


def meta_redirect(html):
  """Check the HTML for a http-equiv refresh in a meta tag, and return it if
  present. If none is found, return None."""
  parser = RefreshParser()
  parser.feed(html)
  return parser.get_url()

class RefreshParser(HTMLParser.HTMLParser):
  def __init__(self):
    HTMLParser.HTMLParser.__init__(self)
    self.url = None
  def get_url(self):
    return self.url
  def handle_starttag(self, tag, attrs):
    """Reminder of what we're looking for:
    <meta http-equiv="refresh" content="0;url=http://url.com" />
    attrs = [('http-equiv', 'refresh'), ('content', '0;url=http://url.com')]
    """
    refresh = False
    if tag == 'meta':
      attrs_dict = dict(attrs)
    else:
      return
    if attrs_dict.get('http-equiv') == 'refresh':
      content = attrs_dict.get('content', '')
    else:
      return
    url_index = content.lower().find('url=') + len('url=')
    if url_index >= len('url='):
      self.url = content[url_index:]
    else:
      return


def get_columns(default=None):
  """Get current terminal width, using stty command. If stty isn't available,
  or if it gives an error, return the default."""
  if not distutils.spawn.find_executable('stty'):
    return default
  devnull = open(os.devnull, 'wb')
  try:
    output = subprocess.check_output(['stty', 'size'], stderr=devnull)
  except OSError:
    devnull.close()
    return default
  devnull.close()
  try:
    return int(output.split()[1])
  except ValueError:
    return default

def fail(message):
  sys.stderr.write(message+"\n")
  sys.exit(1)


if __name__ == "__main__":
  main()
