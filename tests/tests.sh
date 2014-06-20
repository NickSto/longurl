#!/usr/bin/env bash
dirname=$(dirname $0)

if $dirname/../longurl.py 'http://bit.ly/1c9r7Bt' | sed -E 's/(siteID=dZCX6Je2w8Q)-[A-Za-z0-9_.]+$/\1/i' | diff - $dirname/bit.ly-1c9r7Bt.out; then
  echo 'pass: http://bit.ly/1c9r7Bt'
else
  echo 'FAIL: http://bit.ly/1c9r7Bt'
fi
if $dirname/../longurl.py 'http://bit.ly/18bArwp' | sed -E 's#^(http://(cj\.dotomi|www\.emjcd)\.com/).*$#\1#' | diff - $dirname/bit.ly-18bArwp.out; then
  echo 'pass: http://bit.ly/18bArwp'
else
  echo 'FAIL: http://bit.ly/18bArwp'
fi
if $dirname/../longurl.py 'http://bit.ly/1iKbWfU' | sed -E 's/(siteID=dZCX6Je2w8Q)-[A-Za-z0-9_.]+$/\1/i' | diff - $dirname/bit.ly-1iKbWfU.out; then
  echo 'pass: http://bit.ly/1iKbWfU'
else
  echo 'FAIL: http://bit.ly/1iKbWfU'
fi
if $dirname/../longurl.py 'http://bit.ly/HtZ9lX' | sed -E 's#^(http://(cj\.dotomi|www\.emjcd)\.com/).*$#\1#' | sed -E 's/(referralID=)[0-9a-f-]+$/\1/' | diff - $dirname/bit.ly-HtZ9lX.out; then
  echo 'pass: http://bit.ly/HtZ9lX'
else
  echo 'FAIL: http://bit.ly/HtZ9lX'
fi
if $dirname/../longurl.py 'http://bit.ly/1aYLVck' | diff - $dirname/bit.ly-1aYLVck.out; then
  echo 'pass: http://bit.ly/1aYLVck'
else
  echo 'FAIL: http://bit.ly/1aYLVck'
fi
if $dirname/../longurl.py 'http://ift.tt/1gLewTn' | diff - $dirname/ift.tt-1gLewTn.out; then
  echo 'pass: http://ift.tt/1gLewTn'
else
  echo 'FAIL: http://ift.tt/1gLewTn'
fi
if $dirname/../longurl.py 'http://zdbb.net/u/pd' | diff - $dirname/zdbb.net-u-pd.out; then
  echo 'pass: http://zdbb.net/u/pd'
else
  echo 'FAIL: http://zdbb.net/u/pd'
fi
if $dirname/../longurl.py 'http://zdbb.net/u/27t' | sed -E 's/ut=[0-9a-f]+$/ut=/' | sed -E 's/guid=[0-9a-f-]+&//' | diff - $dirname/zdbb.net-u-27t.out; then
  echo 'pass: http://zdbb.net/u/27t'
else
  echo 'FAIL: http://zdbb.net/u/27t'
fi
if $dirname/../longurl.py 'http://zdbb.net/u/2aq' | diff - $dirname/zdbb.net-u-2aq.out; then
  echo 'pass: http://zdbb.net/u/2aq'
else
  echo 'FAIL: http://zdbb.net/u/2aq'
fi
