# -*- coding: utf-8 -*-
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import scrapy


def update_url_query(url, query):
    parsed = list(urlparse(url))
    qs_items = dict(parse_qsl(parsed[4]))
    qs_items.update(query.items())
    parsed[4] = urlencode(qs_items)

    return urlunparse(parsed)


def update_limit_qs(link, limit=72):
    return update_url_query(link, {'limit': limit})


class RyanscomputersSpider(scrapy.Spider):
    name = 'RyansComputers'
    allowed_domains = ['ryanscomputers.com', 'www.ryanscomputers.com']
    start_urls = ['https://ryanscomputers.com']

    def parse(self, response):
        for item in response.css(".nav-item")[1:]:
            category = item.css('::text').get().strip()
            subcategory1 = None
            for anchor in item.css('a'):
                subcategory1 = anchor.css(
                    "::text").get().strip() if anchor.attrib['class'] == "head-menu"\
                    else subcategory1
                subcategory2 = None
                if anchor.attrib['class'] == 'nav-link':
                    subcategory2 = anchor.css('::text').get().strip()

                link = anchor.css("::attr(href)").get()
                path = urlparse(link).path
                if link == "javascript:void(0);" or\
                        not path.startswith('/grid') or\
                        path.startswith('/grid/all-'):
                    continue

                yield response.follow(
                    update_limit_qs(link),
                    self.parse_grid, cb_kwargs={
                        'category': category,
                        'subcategory1': subcategory1,
                        'subcategory2': subcategory2,
                    }
                )

    def parse_grid(self, response, category, subcategory1, subcategory2):
        next_page = response.css("a[rel=next]::attr(href)").get()
        if next_page:
            yield response.follow(update_limit_qs(next_page), self.parse_grid, cb_kwargs={
                'category': category,
                'subcategory1': subcategory1,
                'subcategory2': subcategory2,
            })

        for link in response.css(".product-title-grid::attr(href)").extract():
            yield response.follow(link, self.parse_product, cb_kwargs={
                'category': category,
                'subcategory1': subcategory1,
                'subcategory2': subcategory2,
            })

    def parse_product(self, response, category, subcategory1, subcategory2):
        details = response.css('.produc-details-short')
        reviews = []
        for comment in response.css('.comments'):
            reviews.append({
                'stars': len(comment.css('.fa-star')),
                'username': comment.css('p > span::text').get().strip(),
                'comment': (comment.css('p:last-child::text').get() or '').strip(),
            })

        specs = {}
        for tr in response.css('.information')[0].css('tr'):
            specs[tr.css('td:first-child::text').get().strip()] =\
                tr.css('td:last-child::text').get().strip()

        yield {
            'title': details.css(".title::text").get().strip(),
            'reviews': reviews,
            'category': category,
            'subcategory1': subcategory1,
            'subcategory2': subcategory2,
            'productId': details.css("p > span::text").get().strip(),
            'priceOld': (details.css('.old-price::text').get() or '0').strip(),
            'price': (details.css('.price::text').get() or '0').strip(),
            'specs': specs,
        }
