import string
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from lxml import etree


def update_url_query(url, query):
    parsed = list(urlparse(url))
    qs_items = dict(parse_qsl(parsed[4]))
    qs_items.update(query.items())
    parsed[4] = urlencode(qs_items)

    return urlunparse(parsed)


def extract_locations(xml):
    et = etree.fromstring(xml)
    for location in et.xpath(
            './n:url/n:loc/text()', namespaces={'n': et.nsmap[None]}):
        yield location


def remove_puncts(text):
    return ''.join([' ' if c in string.punctuation else c for c in text])


class UniqueFollowMixin:
    visited = set()

    def follow_once(self, response, url, *args, **kwargs)
        url = url.lower().strip()
        if url not in self.visited:
            self.visited.add(url)
            return response.follow(url, *args, **kwargs)
        return None
