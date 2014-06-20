#!/usr/bin/env bash
dirname=$(dirname $0)

SIMPLE_URLS="
http://t.co/mWfAwPy5O7
http://bit.ly/1aYLVck
http://ift.tt/1gLewTn
http://zdbb.net/u/pd
http://zdbb.net/u/2aq"

# The straightforward ones
for url in $SIMPLE_URLS; do
  filename=$(echo "$url" | sed -E 's#^https?://##' | sed -E 's#/#-#g').out
  if $dirname/../longurl.py -W 80 "$url" | diff - $dirname/$filename; then
    echo "pass: $url"
  else
    echo "FAIL: $url"
  fi
done

# The complicated ones
if $dirname/../longurl.py -W 80 'http://t.co/2V0HctQdnr' | sed -E 's#^(http://ohmyyy.gt/scmf/)[A-Za-z0-9_-]+/#\1/#' | diff - $dirname/t.co-2V0HctQdnr.out; then
  echo 'pass: http://t.co/2V0HctQdnr'
else
  echo 'FAIL: http://t.co/2V0HctQdnr'
fi
if $dirname/../longurl.py -W 80 'http://bit.ly/1c9r7Bt' | sed -E 's/(siteID=dZCX6Je2w8Q)-[A-Za-z0-9_.]+$/\1/i' | diff - $dirname/bit.ly-1c9r7Bt.out; then
  echo 'pass: http://bit.ly/1c9r7Bt'
else
  echo 'FAIL: http://bit.ly/1c9r7Bt'
fi
if $dirname/../longurl.py -W 80 'http://bit.ly/18bArwp' | sed -E 's#^(http://(cj\.dotomi|www\.emjcd)\.com/).*$#\1#' | diff - $dirname/bit.ly-18bArwp.out; then
  echo 'pass: http://bit.ly/18bArwp'
else
  echo 'FAIL: http://bit.ly/18bArwp'
fi
if $dirname/../longurl.py -W 80 'http://bit.ly/1iKbWfU' | sed -E 's/(siteID=dZCX6Je2w8Q)-[A-Za-z0-9_.]+$/\1/i' | diff - $dirname/bit.ly-1iKbWfU.out; then
  echo 'pass: http://bit.ly/1iKbWfU'
else
  echo 'FAIL: http://bit.ly/1iKbWfU'
fi
if $dirname/../longurl.py -W 80 'http://bit.ly/HtZ9lX' | sed -E 's#^(http://(cj\.dotomi|www\.emjcd)\.com/).*$#\1#' | sed -E 's/(referralID=)[0-9a-f-]+$/\1/' | diff - $dirname/bit.ly-HtZ9lX.out; then
  echo 'pass: http://bit.ly/HtZ9lX'
else
  echo 'FAIL: http://bit.ly/HtZ9lX'
fi
# only tests the final url:
if $dirname/../longurl.py -Q 'http://zdbb.net/u/27t' | sed -E 's/&/\n/g' | sort | diff - $dirname/zdbb.net-u-27t.out; then
  echo 'pass: http://zdbb.net/u/27t'
else
  echo 'FAIL: http://zdbb.net/u/27t'
fi
