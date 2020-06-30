#!/usr/bin/env python3
import argparse
import collections
import distutils.spawn
import html.parser
import logging
import os
import re
import requests
import socket
import subprocess
import sys
import urllib.parse
import webbrowser

COLUMNS_DEFAULT = 80
SCHEME_REGEX = r'^[^?#:]+://'
URL_REGEX = r'^(https?://)?([a-zA-Z0-9-]+\.)+[a-zA-Z0-9]+(/\S*)?$'
USER_AGENT_BROWSER = (
  'Mozilla/5.0 (Windows NT 10.1; Win64; x64; rv:32.0) Gecko/20100101 Firefox/73.0'
)
USER_AGENT_CUSTOM = 'longurl.py'
#TODO: Use good list of headers (some of these can cause problems):
# headers = {
#   'Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
#   'Accept-Language':'en-US,en;q=0.5',
#   'Accept-Encoding':'gzip, deflate',
#   'Connection':'keep-alive',
# }

DESCRIPTION = """Follow the chain of redirects from the starting url.
By default, this will print to stdout the start url, then every redirect in the chain.
You can omit the 'http://' from the url argument. If no url is given on the command line, it will
try to use xclip to find it on the clipboard."""


def make_argparser():
  parser = argparse.ArgumentParser(description=DESCRIPTION)
  parser.add_argument('url', metavar='http://sho.rt/url', nargs='?', default=url_from_clipboard(),
    help='The short url. If not given, this will use xclip to search for a url in your clipboard.')
  parser.add_argument('-m', '--max-redirects', type=int, default=200,
    help='Maximum number of redirects to process. Give "0" to set no limit. Default: %(default)s.')
  parser.add_argument('-c', '--clipboard', action='store_true',
    help='Copy the final domain to the clipboard (or the full url if using --browser).')
  parser.add_argument('-b', '--browser', action='store_true',
    help='Open your default browser at the end to a reputation-checking site for the final domain. '
      'Also, the full final url will be placed on the clipboard instead of just the domain.')
  parser.add_argument('-r', '--reputation-url', default='https://www.mywot.com/en/scorecard/',
    help='The url to prepend to the domain name for checking the reputation of the domain. '
      'Default: %(default)s')
  parser.add_argument('-u', '--fake-user-agent', dest='user_agent', action='store_const',
    const=USER_AGENT_BROWSER, default=USER_AGENT_CUSTOM,
    help='Use a Firefox user agent string instead of the script\'s own custom user agent ('
      f"{USER_AGENT_CUSTOM!r}). Counterintuitively, many url shorteners (including Twitter's t.co) "
      'react better to unrecognized user agents (fewer meta refreshes). But in case some reject '
      'unrecognized ones, you can use this to pretend to be a normal browser. The Firefox user '
      f'agent string is {USER_AGENT_BROWSER!r}.')
  parser.add_argument('-M', '--max-response', type=int, default=128,
    help='Maximum amount of response to download, looking for meta refreshes in the HTML. Given in '
      'kilobytes. Default: %(default)s kb.')
  parser.add_argument('-W', '--terminal-width', type=int, default=get_columns(COLUMNS_DEFAULT),
    help='Manually tell the script the number of columns in the terminal.')
  parser.add_argument('-l', '--log', type=argparse.FileType('w'), default=sys.stderr,
    help='Print log messages to this file instead of to stderr. Warning: Will overwrite the file.')
  volume = parser.add_mutually_exclusive_group()
  volume.add_argument('-q', '--quiet', dest='volume', action='store_const', const=logging.ERROR,
    default=logging.INFO,
    help='Only print the final url to stdout and suppress all stderr messages but the most '
      'important.')
  volume.add_argument('-v', '--verbose', dest='volume', action='store_const', const=logging.INFO)
  volume.add_argument('-D', '--debug', dest='volume', action='store_const', const=logging.DEBUG)
  return parser


def main(argv):

  parser = make_argparser()
  args = parser.parse_args(argv[1:])

  logging.basicConfig(stream=args.log, level=args.volume, format='%(message)s')

  clipboard = args.clipboard
  if not distutils.spawn.find_executable('xclip'):
    logging.warning(
      'Warning: Could not find `xclip` command. Will not be able to copy final url to clipboard.'
    )
    clipboard = False

  #TODO: read from stdin
  url = args.url
  if url is None:
    parser.print_help()
    raise URLError('Error: No url argument given and could not find a valid url in clipboard.')

  if not urllib.parse.urlsplit(url).scheme:
    url = 'http://'+url
  if get_loglevel() <= logging.WARNING:
    print(url)

  # Do the actual redirect resolution.
  replies = list(follow_redirects(url, max_response=args.max_response, user_agent=args.user_agent))
  for reply_num, reply in enumerate(replies):
    if get_loglevel() <= logging.WARNING or reply_num == len(replies)-1:
      print(reply.location)

  # Remove starting www. from domain, if present
  domain = urllib.parse.urlsplit(reply.location).netloc
  if domain.startswith('www.') and domain.count('.') > 1:
      domain = domain[4:]

  # Print summary info.
  for reply in replies:
    if reply.type == 'refresh':
      logging.info('meta refresh from  '+reply.url[:args.terminal_width-19])
    elif reply.type == 'absolute':
      logging.info('absolute path from '+reply.url[:args.terminal_width-19])
    elif reply.type == 'relative':
      logging.info('relative path from '+reply.url[:args.terminal_width-19])
  logging.info(f'total redirects: {len(replies)}')

  # Copy final data to clipboard, and open reputation checker in browser, if requested.
  if clipboard:
    if args.browser:
      to_clipboard(reply.location)
    else:
      to_clipboard(domain)
  if args.browser:
    webbrowser.open(args.reputation_url+domain)


# THE MAIN LOGIC

Reply = collections.namedtuple('Reply', ('url', 'type', 'code', 'location'))
Reply.__doc__ = """This represents a response from a server, focusing on its redirection.
`url`: The request url (who the reply is from).
`type`: The type of redirect: `absolute`, `relative`, or `refresh`.
`code`: The HTTP response code received.
`location`: The URL that the server is redirecting to.
"""

def follow_redirects(url, user_agent=USER_AGENT_CUSTOM, max_redirects=200, max_response=128):
  """Follow a chain of url redirects.
  A generator which yields one `Reply` object per redirect it receives.
  It does not yield anything for the final request, since it won't be a redirect."""
  reply_type = last_code = last_url = None
  for resp_num, response in enumerate(get_responses(url, user_agent, max_redirects, max_response)):
    if resp_num > 0:
      # Finish processing the previous reply and yield it.
      if reply_type is None:
        # We didn't see a 'Location:' header. But since we're now at the next response,
        # the only way we could've another response is through a redirect. And the only non-Location
        # type of redirect we currently support is via a <meta> refresh.
        reply_type = 'refresh'
      yield Reply(type=reply_type, code=last_code, location=response.url, url=last_url)
      reply_type = last_code = None
    location = get_location(response)
    if location:
      reply_type = url_type(location)
    last_url = response.url
    last_code = response.status_code


def get_responses(url, user_agent, max_redirects, max_response):
  headers = {'User-Agent':user_agent}
  num_redirects = 0
  while num_redirects < max_redirects or max_redirects == 0:
    num_redirects += 1
    # Make request.
    try:
      final_response = requests.get(url, headers=headers)
    except requests.exceptions.RequestException:
      logging.critical(f'Error requesting {url!r}')
      raise
    # Yield all urls in the redirect chain that `requests` was able to follow.
    for response in final_response.history:
      yield response
    # Check for meta refreshes.
    if final_response.status_code == 200:
      url = get_meta_redirect(final_response, max_response)
    else:
      raise URLError(
        f'Non-200 status and no Location header. Status message:\n\t{final_response.status_code}: '
        f'{final_response.reason}'
      )
    yield final_response
    if not url:
      break


def get_location(response):
  locations = response.headers.get('location')
  if locations:
    # It's possible they gave more than one Location: header.
    return locations.split(',')[0]
  else:
    return None


def url_type(url):
  if url.startswith('/') or re.search(SCHEME_REGEX, url):
    return 'absolute'
  else:
    return 'relative'


def url_from_clipboard():
  """Use xclip to copy the short url from the clipboard.
  Checks it against a simple, broad URL regex, and returns None if no match.
  Also returns None on error executing the xclip command."""
  if not distutils.spawn.find_executable('xclip'):
    return None
  try:
    output = subprocess.check_output(['xclip', '-o', '-sel', 'clip'], encoding='utf8')
  except (OSError, subprocess.CalledProcessError):
    return None
  if re.search(URL_REGEX, output):
    return output
  else:
    return None


def to_clipboard(domain):
  """Use xclip to copy the domain to the clipboard."""
  process = subprocess.Popen(['xclip', '-sel', 'clip'], encoding='utf8', stdin=subprocess.PIPE)
  process.communicate(input=domain)


def get_meta_redirect(response, max_response):
  html = response.text[:max_response*1024]
  try:
    meta_url = parse_meta_redirect(html)
  except Exception as error:
    logging.error(f'Error parsing HTML: {error}')
    meta_url = None
  return meta_url


def parse_meta_redirect(html):
  """Check the HTML for a http-equiv refresh in a meta tag, and return it if
  present. If none is found, return None."""
  parser = RefreshParser()
  parser.feed(html)
  return parser.url


class RefreshParser(html.parser.HTMLParser):
  def __init__(self):
    super().__init__()
    self.url = None

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
  try:
    output = subprocess.check_output(['stty', 'size'], stderr=subprocess.DEVNULL, encoding='utf8')
  except (OSError, subprocess.CalledProcessError):
    return default
  try:
    return int(output.split()[1])
  except ValueError:
    return default


def get_loglevel():
  return logging.getLogger().getEffectiveLevel()


class URLError(Exception):
  def __init__(self, message=None):
    if message:
      super().__init__(self, message)


if __name__ == "__main__":
  try:
    main(sys.argv)
  except KeyboardInterrupt:
    pass
