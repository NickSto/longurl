longurl
=======

For various reasons, you might want to see where a url goes before you click it. Sometimes it's a shortened url and you're not sure where you'll end up. Is it a safe site? Sometimes it might be an advertiser link and you're wondering whose tracking domains you'll be routed through.

This script will automatically make a request to the url you give it, and repeatedly follow any redirects until they end on a terminal page. It can handle HTTP-level redirects using response codes like 301 and 302, and it even detects any redirects done in the HTML of a page using &lt;meta&gt; tags. It has been tested on a variety of domains, including advertiser links using up to 14 consecutive redirects! That's the sort of thing going on behind the scenes sometimes when you click. This little script helps you pull back the curtain.
