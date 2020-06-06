import string
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


def update_url_query(url, query):
    parsed = list(urlparse(url))
    qs_items = dict(parse_qsl(parsed[4]))
    qs_items.update(query.items())
    parsed[4] = urlencode(qs_items)

    return urlunparse(parsed)


def remove_puncts(text):
    return ''.join([' ' if c in string.punctuation else c for c in text])
