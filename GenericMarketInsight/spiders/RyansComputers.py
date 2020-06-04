# -*- coding: utf-8 -*-
import logging
import string
from time import sleep
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


def remove_puncts(text):
    return ''.join([' ' if c in string.punctuation else c for c in text])


class RyanscomputersSpider(scrapy.Spider):
    name = 'RyansComputers'
    allowed_domains = ['ryanscomputers.com', 'www.ryanscomputers.com']
    start_urls = ['https://ryanscomputers.com']
    brand_cache = {}
    brand_cache_completion = 0
    brands = set()

    def parse_and_populate_brand_cache(self, response, brand):
        self.brand_cache[response.css(
            '.product-logo img::attr(src)').get()] = brand
        self.brand_cache_completion -= 1
        self.brands.add(brand)
        yield {
            'brand_name': brand,
        }

    def parse(self, response):
        # Populate url-brand dictionary.
        selection = response.css('#brandsModal li a')
        self.brand_cache_completion = len(selection)
        for brand in selection:
            yield response.follow(
                brand.css('::attr(href)').get().strip(),
                self.parse_and_populate_brand_cache, cb_kwargs={
                    'brand': brand.css('::text').get().strip(),
                })

        self.log("{} BRANDS AVAILABLE".format(
            self.brand_cache_completion), logging.INFO)

        # Wait until populated
        while self.brand_cache_completion != 0:
            sleep(0.01)
            yield None

        self.log("BRAND CACHE DONE ({} BRANDS)".format(
            len(self.brand_cache)), logging.INFO)

        # Item parsing and yielding starts form here.
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

    def match_brand(self, title):
        for brand_filter in self.brands:
            if remove_puncts(title.lower()).startswith(
                    remove_puncts(brand_filter.lower())):
                return brand_filter
        self.log("NO BRANDS FOR {}".format(title), logging.WARNING)
        return None

    def parse_grid(self, response, category, subcategory1, subcategory2):
        next_page = response.css("a[rel=next]::attr(href)").get()
        if next_page:
            yield response.follow(
                update_limit_qs(next_page), self.parse_grid, cb_kwargs={
                    'category': category,
                    'subcategory1': subcategory1,
                    'subcategory2': subcategory2,
                })

        brand_filters = [brand.strip() for brand in response.css(
            '.default-brand-filters button::text').extract()
            if brand.strip() not in self.brands]

        for brand in brand_filters:
            self.brands.add(brand)
            yield {
                'brand_name': brand,
            }

        brand_filters.extend(self.brand_cache.values())

        for box in response.css(".product-box"):
            cache_hit = self.brand_cache.get(
                box.css('.product-logo img::attr(src)').get())
            yield response.follow(
                box.css('.product-title-grid::attr(href)').get(),
                self.parse_product, cb_kwargs={
                    'category': category,
                    'subcategory1': subcategory1,
                    'subcategory2': subcategory2,
                    'brand': cache_hit if cache_hit else self.match_brand(
                        box.css('.product-title-grid::text').get()),
                })

    def parse_product(self, response, category, subcategory1, subcategory2, brand):
        details = response.css('.produc-details-short')
        reviews = []
        for comment in response.css('.comments'):
            reviews.append({
                'rating': len(comment.css('.fa-star')),
                'username': comment.css('p > span::text').get().strip(),
                'comment': (comment.css('p:last-child::text').get() or '').strip(),
            })

        specs = {}
        for tr in response.css('.information')[0].css('tr'):
            specs[tr.css('td:first-child::text').get().strip()] =\
                tr.css('td:last-child::text').get().strip()

        yield {
            'id': details.css("p > span::text").get().strip(),
            'title': details.css(".title::text").get().strip(),
            'reviews': reviews,
            'category': category,
            'subcategory1': subcategory1,
            'subcategory2': subcategory2,
            'brand': brand,
            'price_old': (details.css('.old-price::text').get() or '0').strip(),
            'price': (details.css('.price::text').get() or '0').strip(),
            'specifications': specs,
        }
