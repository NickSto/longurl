#!/usr/bin/env python
import re
import os
import urllib
import httplib
import urlparse
import argparse
import subprocess
import HTMLParser
import webbrowser
import distutils.spawn

COLUMNS_DEFAULT = 80
SCHEME_REGEX = r'^[^?#:]+://'
URL_REGEX = r'^(https?://)?([a-zA-Z0-9-]+\.)+[a-zA-Z0-9]+(/\S*)?$'

OPT_DEFAULTS = {'quiet':False, 'custom_ua':False, 'max_response':128, 'max_redirects':200,
                'reputation_url':'https://www.mywot.com/en/scorecard/'}
DESCRIPTION = """Follow the chain of redirects from the starting url. This will print the start url,
then every redirect in the chain. Can omit the 'http://' from the url argument. If no url is given
on the command line, it will try to use xclip to find it on the clipboard."""
USER_AGENT_BROWSER = ('Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:32.0) Gecko/20100101 '
                      'Firefox/40.0')
USER_AGENT_CUSTOM = 'longurl.py'
#TODO: Use good list of headers (some of these can cause problems):
# headers = {
#   'Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
#   'Accept-Language':'en-US,en;q=0.5',
#   'Accept-Encoding':'gzip, deflate',
#   'Connection':'keep-alive',
# }
headers = {}


def main():

  parser = argparse.ArgumentParser(description=DESCRIPTION)
  parser.set_defaults(**OPT_DEFAULTS)

  parser.add_argument('url', metavar='http://sho.rt/url', nargs='?',
    help='The short url. If not given, this will use xclip to search for a url in your clipboard.')
  parser.add_argument('-m', '--max-redirects', type=int,
    help='Maximum number of redirects to process. Give "0" to set no limit. Default: %(default)s.')
  parser.add_argument('-q', '--quiet', action='store_true',
    help='Suppress all output but the list of urls. The number of output lines will be 1 + the '
         'number of redirects.')
  parser.add_argument('-Q', '--very-quiet', action='store_true',
    help='Suppress all output but the final url.')
  parser.add_argument('-c', '--clipboard', action='store_true',
    help='Copy the final domain to the clipboard (or the full url if using --browser).')
  parser.add_argument('-p', '--percent-decode', action='store_true',
    help='Decode percent-encoded characters in the redirect URL.')
  parser.add_argument('-b', '--browser', action='store_true',
    help='Open your default browser at the end to a reputation-checking site for the final domain. '
         'Also, the full final url will be placed on the clipboard instead of just the domain.')
  parser.add_argument('-r', '--reputation-url',
    help='The url to prepend to the domain name for checking the reputation of the domain. '
         'Default: %(default)s')
  parser.add_argument('-u', '--fake-user-agent', action='store_true',
    help='Use a Firefox user agent string instead of the script\'s own custom user agent ("'
         +USER_AGENT_CUSTOM+'"). Counterintuitively, many url shorteners (including Twitter\'s '
         't.co) react better to unrecognized user agents (fewer meta refreshes). But in case some '
         'reject unrecognized ones, you can use this to pretend to be a normal browser. The '
         'Firefox user agent string is "'+USER_AGENT_BROWSER+'".')
  parser.add_argument('-M', '--max-response', type=int,
    help='Maximum amount of response to download, looking for meta refreshes in the HTML. Given in '
         'kilobytes. Default: %(default)s kb.')
  parser.add_argument('-W', '--terminal-width', type=int,
    help='Manually tell the script the number of columns in the terminal.')

  args = parser.parse_args()

  if not distutils.spawn.find_executable('xclip'):
    args.no_clipboard = True

  if args.fake_user_agent:
    user_agent = USER_AGENT_BROWSER
  else:
    user_agent = USER_AGENT_CUSTOM

  if args.terminal_width:
    columns = args.terminal_width
  else:
    columns = get_columns(COLUMNS_DEFAULT)

  #TODO: read from stdin
  if args.url:
    url = args.url
  else:
    url = url_from_clipboard()
    if url is None:
      parser.print_help()
      raise URLError('Error finding valid url in clipboard.')

  if not re.search(SCHEME_REGEX, url):
    url = 'http://'+url

  # Do the actual redirect resolution.
  events = []
  redirects = -1
  for url, these_events in follow_redirects(url, percent_decode=args.percent_decode,
                                            max_response=args.max_response, user_agent=user_agent):
    if not args.very_quiet:
      print url
    events.extend(these_events)
    redirects += 1

  if args.very_quiet:
    print url

  # Remove starting www. from domain, if present
  domain = urlparse.urlsplit(url)[1]
  if domain.startswith('www.') and domain.count('.') > 1:
      domain = domain[4:]

  # Print summary info.
  if not args.quiet:
    for event in events:
      if event['type'] == 'refresh':
        print 'meta refresh from  '+event['url'][:columns-19]
      elif event['type'] == 'absolute':
        print 'absolute path from '+event['url'][:columns-19]
      elif event['type'] == 'relative':
        print 'relative path from '+event['url'][:columns-19]
    print 'total redirects: {}'.format(redirects)

  # Copy final data to clipboard, and open reputation checker in browser, if requested.
  if args.clipboard:
    if args.browser:
      to_clipboard(url)
    else:
      to_clipboard(domain)
  if args.browser:
    webbrowser.open(args.reputation_url+domain)


# THE MAIN LOGIC
def follow_redirects(url, percent_decode=False, max_response=128, user_agent=USER_AGENT_CUSTOM,
                     max_redirects=200):
  """Follow a chain of url redirects.
  A generator which yields, for every redirect, the url, and an informational list of events
  occurring during that redirection.
  Includes the input url as the first returned url."""
  headers = {'User-Agent':user_agent}
  events = []
  redirects = 0
  while redirects < max_redirects or max_redirects == 0:
    redirects += 1

    yield url, events
    events = []

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
      raise URLError("Unrecognized URI scheme in:\n"+url)
    # Note: both of these steps can throw exceptions
    conex.request('GET', path, '', headers)
    response = conex.getresponse()

    redirect_url = response.getheader('Location')

    # Check for meta refresh
    if redirect_url is None:
      if response.status == 200:
        html = response.read(max_response * 1024)
        try:
          meta_url = meta_redirect(html)
        except Exception:
          meta_url = None  # on error, proceed as if none was found
        if meta_url:
          events.append({'type':'refresh', 'url':url})
          redirect_url = meta_url
        else:
          # If no Location header and no meta refresh, then we're at the end
          break
      else:
        raise URLError("Non-200 status and no Location header. Status message:\n\t{}: {}"
                       .format(response.status, response.reason))
    conex.close()

    # Fix percent-encoded and relative urls
    if redirect_url:
      # Try to tell when it's a percent-encoded (or force with --percent-decode)
      if (redirect_url.startswith('http%3A%2F%2F') or
          redirect_url.startswith('https%3A%2F%2F') or
          percent_decode):
        redirect_url = urllib.unquote(redirect_url)
      if not re.search(SCHEME_REGEX, redirect_url):
        if redirect_url.startswith('/'):
          events.append({'type':'absolute', 'url':url})
        else:
          events.append({'type':'relative', 'url':url})
      url = urlparse.urljoin(url, redirect_url)
    # Try to do some limited percent encoding of always-invalid characters
    url = url.replace(' ', '%20')


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
    """Process each tag, returning any redirect url found in a <meta>.
    Example of what it looks for:
    <meta http-equiv="refresh" content="0;url=http://url.com" />"""
    if tag != 'meta':
      return
    attrs_dict = dict(attrs)
    # Find an "http-equiv" attribute with value "refresh"
    if attrs_dict.get('http-equiv') == 'refresh':
      content = attrs_dict.get('content', '')
    else:
      return
    # Extract the url
    url_index = content.lower().find('url=') + len('url=')
    if url_index >= len('url='):
      self.url = content[url_index:]
    else:
      return


def get_columns(default=80):
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


class URLError(Exception):
  def __init__(self, message=None):
    if message:
      Exception.__init__(self, message)


if __name__ == "__main__":
  try:
    main()
  except KeyboardInterrupt:
    pass
