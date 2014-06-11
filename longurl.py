#!/usr/bin/env python
# 
# Example short urls:
# http://t.co/oZ2IWUfW9m - relatively sane - should end at gift-card-rewards.com
# - update: oops, disabled!
# http://bit.ly/1b5KFTr - 14 redirects! - should end at www.nextag.com
# - oops, looks like it might've expired; only 7 redirects now.
# http://bit.ly/1c9r7Bt - meta refresh - actually ends at www.toshiba.com
# - Careful, they can detect you re-using urls partway through
#   the chain (session ids) and give you a different redirect or a 500
# http://bit.ly/18bArwp - meta refresh - ends at accessories.us.dell.com
# - via zdbb.net, who might be responsible for the blocking of the last one
# http://bit.ly/1a9xteY - relative Location - ends at accessories.us.dell.com
# - and the location doesn't start with a /
# http://bit.ly/1iKbWfU
# http://bit.ly/HtZ9lX
# - both include a Location header with a space character
# http://bit.ly/1aYLVck - HTMLParser throws a UnicodeDecodeError
# Bad byte in html of http://shop.lenovo.com/us/en/laptops/thinkpad/x-series/x1-carbon-touch/?cid=US:display:lDtDOc&dfaid=1
# http://ift.tt/1gLewTn - gives "Unrecognized URI scheme" when it requests:
# https://www.facebook.com/photo.php?fbid=10152572961694741&set=a.10152523012949741.1073741826.699139740&type=1
# http://zdbb.net/u/pd - meta redirect contains percent-encoded url:
# - http%3A%2F%2Fadfarm.mediaplex.com%2Fad%2Fck%2F12309-196588-3601-49%3FDURL%3Dhttp%253A%252F%252Fwww.dell.com%252Fus%252Fp%252Fxps-11-9p33%252Fpd.aspx%253F~ck%253Dmn
#TODO: read from stdin, add option to only print final url
import os
import re
import sys
import urllib
import httplib
import urlparse
import argparse
import subprocess
import HTMLParser
import distutils.spawn

COLUMNS_DEFAULT = 80
SCHEME_REGEX = r'^[^?#:]+://'
URL_REGEX = r'^(https?://)?([a-zA-Z0-9-]+\.)+[a-zA-Z0-9]+(/\S*)?$'
REPUTATION_URL = 'https://www.mywot.com/en/scorecard/'

OPT_DEFAULTS = {'quiet':False, 'custom_ua':False, 'max_response_read':128}
DESCRIPTION = """Follow the chain of redirects from the starting url. This
will print the start url, then every redirect in the chain. Can omit the
'http://' from the url argument. If no url is given on the command line, it
will try to use xclip to find it on the clipboard."""
EPILOG="""Set the $DEBUG environment variable to "true" to run in debug mode."""
USER_AGENT_BROWSER = ('Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:32.0) '
  'Gecko/20100101 Firefox/32.0')
USER_AGENT_CUSTOM = 'longurl.py'
# Some of the headers in the full list can cause problems:
# headers = {
#   'Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
#   'Accept-Language':'en-US,en;q=0.5',
#   'Accept-Encoding':'gzip, deflate',
#   'Connection':'keep-alive',
# }
headers = {}

# set debug as a global
debug = os.environ.get('DEBUG')

def main():

  parser = argparse.ArgumentParser(description=DESCRIPTION, epilog=EPILOG)
  parser.set_defaults(**OPT_DEFAULTS)

  parser.add_argument('url', metavar='http://sho.rt/url', nargs='?',
    help='The short url. If not given, this will use xclip to search for a url '
      'in your clipboard.')
  parser.add_argument('-q', '--quiet', action='store_true',
    help='Suppress all output but the list of urls. The number of output lines '
      'will be 1 + the number of redirects.')
  parser.add_argument('-Q', '--very-quiet', action='store_true',
    help='Suppress all output but the final url.')
  parser.add_argument('-c', '--clipboard', action='store_true',
    help='Copy the final domain to the clipboard (or the full url if using '
      '--firefox).')
  parser.add_argument('-f', '--firefox', action='store_true',
    help='Open Firefox at the end to a reputation-checking site (mywot.com) '
      'for the final domain. Also, the full final url will be placed on the '
      'clipboard instead of just the domain.')
  parser.add_argument('-u', '--fake-user-agent', action='store_true',
    help='Use a Firefox user agent string instead of the script\'s own custom '
      'user agent ("'+USER_AGENT_CUSTOM+'"). Counterintuitively, many url '
      'shorteners (including Twitter\'s t.co) react better to unrecognized '
      'user agents (fewer meta refreshes). But in case some reject '
      'unrecognized ones, you can use this to pretend to be a normal browser. '
      'The Firefox user agent string is "'+USER_AGENT_BROWSER+'".')
  parser.add_argument('-m', '--max-response-read', type=int,
    help='Maximum amount of response to download, looking for meta refreshes '
      'in the HTML. Given in kilobytes. Default: %(default)s kb.')

  args = parser.parse_args()

  if not distutils.spawn.find_executable('xclip'):
    args.no_clipboard = True

  if args.fake_user_agent:
    headers['User-Agent'] = USER_AGENT_BROWSER
  else:
    headers['User-Agent'] = USER_AGENT_CUSTOM

  columns = get_columns(COLUMNS_DEFAULT)

  if args.url:
    url = args.url
  else:
    url = url_from_clipboard()
    if url is None:
      parser.print_help()
      fail('\nError finding valid url in clipboard.')

  if not re.search(SCHEME_REGEX, url):
    url = 'http://'+url

  summary = ''
  redirects = 0
  done = False
  while not done:

    if not args.very_quiet:
      print url

    # parse the URL's components
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
    # Note: both of these steps can throw exceptions
    conex.request('GET', path, '', headers)
    response = conex.getresponse()

    redirect_url = response.getheader('Location')

    # Check for meta refresh
    if redirect_url is None:
      if response.status == 200:
        html = response.read(args.max_response_read * 1024)
        try:
          meta_url = meta_redirect(html)
        except Exception:
          meta_url = None   # on error, proceed as if none was found
        if meta_url:
          summary += "meta refresh from  "+url[:columns-19]+"\n"
          redirect_url = meta_url
        else:
          # If no Location header and no meta refresh, then we're at the end
          done = True
      else:
        fail("Error: non-200 status and no Location header. Status message:\n\t"
          +str(response.status)+': '+response.reason)
    conex.close()

    # Fix percent-encoded and relative urls
    if redirect_url:
      if not re.search(SCHEME_REGEX, redirect_url):
        redirect_url = urllib.unquote(redirect_url)
        if redirect_url.startswith('/'):
          summary += "absolute path from "+url[:columns-19]+"\n"
        else:
          summary += "relative path from "+url[:columns-19]+"\n"
      url = urlparse.urljoin(url, redirect_url)

    if not done:
      redirects+=1

  # Remove starting www. from domain, if present
  if domain.startswith('www.') and domain.count('.') > 1:
    domain = domain[4:]

  if args.very_quiet:
    print url
  elif args.quiet:
    pass
  else:
    sys.stdout.write("\n"+summary)
    print "total redirects: "+str(redirects)

  if args.clipboard:
    if args.firefox:
      to_clipboard(url)
    else:
      to_clipboard(domain)

  if args.firefox:
    firefox_check(domain)


def url_from_clipboard():
  """Use xclip to copy the short url from the clipboard.
  Checks it against a simple, broad URL regex, and returns None if no match.
  Also returns None on error executing the xclip command."""
  if not distutils.spawn.find_executable('xclip'):
    return None
  try:
    output = subprocess.check_output(['xclip', '-o', '-sel', 'clip'])
  except (OSError, subprocess.CalledProcessError):
    return None
  if re.search(URL_REGEX, output):
    return output
  else:
    return None


def to_clipboard(domain):
  """Use xclip to copy the domain to the clipboard."""
  process = subprocess.Popen(['xclip', '-sel', 'clip'], stdin=subprocess.PIPE)
  process.communicate(input=domain)


def firefox_check(domain, reputation_url=REPUTATION_URL):
  """Use Firefox to open "reputation_url" + "domain"."""
  if not distutils.spawn.find_executable('firefox'):
    return None
  devnull = open(os.devnull, 'wb')
  try:
    subprocess.call(['firefox', reputation_url+domain], stderr=devnull)
  finally:
    devnull.close()


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
    attrs = [('http-equiv', 'refresh'), ('content', '0;url=http://url.com')]"""
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
