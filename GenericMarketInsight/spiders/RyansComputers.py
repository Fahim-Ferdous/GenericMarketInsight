# -*- coding: utf-8 -*-
import logging
from urllib.parse import urlparse, urljoin

import scrapy

from GenericMarketInsight.utils import remove_puncts, update_url_query, \
    extract_locations, UniqueFollowMixin


def update_limit_qs(link, limit=72):
    return update_url_query(link, {'limit': limit})


class RyanscomputersSpider(scrapy.Spider, UniqueFollowMixin):
    name = 'RyansComputers'
    platform_title = 'Star Tech'
    allowed_domains = ['ryanscomputers.com', 'www.ryanscomputers.com']
    start_urls = ['https://ryanscomputers.com']

    def __init__(self):
        super(RyanscomputersSpider, self).__init__()
        self.brand_cache = {}
        self.brand_cache_completion = 0
        self.brands = set()

    def parse_and_populate_brand_cache(self, response, brand):
        self.brand_cache[response.css(
            '.product-logo img::attr(src)').get()] = brand
        self.brand_cache_completion -= 1
        self.brands.add(brand)
        if self.brand_cache_completion == 0:
            yield response.follow(self.start_urls[0], self.parse_main)
            yield response.follow(
                urljoin(self.start_urls[0], 'category-sitemap.xml'),
                self.parse_category_sitemap)
        # TODO: Parse  products sitemap.

    def parse_category_sitemap(self, response):
        for location in extract_locations(response.body):
            yield self.follow_once(response, location, self.parse_grid)

    def parse(self, response):
        # Populate url-brand dictionary.
        selection = response.css('#brandsModal li a')
        self.brand_cache_completion = len(selection)
        for brand in selection:
            yield self.follow_once(
                response,
                brand.css('::attr(href)').get().strip(),
                self.parse_and_populate_brand_cache, cb_kwargs={
                    'brand': brand.css('::text').get().strip(),
                })

        self.log("{} BRANDS AVAILABLE".format(
            self.brand_cache_completion), logging.INFO)

    def parse_main(self, response):
        self.log("BRAND CACHE DONE ({} BRANDS)".format(
            len(self.brand_cache)), logging.INFO)

        # Item parsing and yielding starts form here.
        for item in response.css(".nav-item")[1:]:
            category = item.css('::text').get().strip()
            subcategory1 = None
            for anchor in item.css('a'):
                subcategory1 = anchor.css("::text").get().strip() \
                    if anchor.attrib['class'] == "head-menu" \
                    else subcategory1
                subcategory2 = None
                if anchor.attrib['class'] == 'nav-link':
                    subcategory2 = anchor.css('::text').get().strip()

                link = anchor.css("::attr(href)").get()
                path = urlparse(link).path
                if link == "javascript:void(0);" or \
                        not path.startswith('/grid') or \
                        path.startswith('/grid/all-'):
                    continue

                yield self.follow_once(
                    response,
                    update_limit_qs(link),
                    self.parse_grid, cb_kwargs={
                        'category': [
                            category,
                            subcategory1,
                            subcategory2,
                        ]
                    }
                )

    def match_brand(self, title):
        for brand_filter in self.brands:
            if remove_puncts(title.lower()).startswith(
                    remove_puncts(brand_filter.lower())):
                return brand_filter
        self.log("NO BRANDS FOR {}".format(title), logging.WARNING)
        return None

    def parse_grid(self, response, category=None):
        if not category:
            category = [None, None, None]
            breadcrumbs = response.css(
                '.breadcrumb-wraper li:not([class=home]) span::text'
            ).extract()
            for i, crumb in enumerate(breadcrumbs):
                if i >= len(category):
                    self.log("Grid <{}> has {} categoricals {}".format(
                        response.request.url, len(breadcrumbs), breadcrumbs),
                        logging.WARNING)
                    break
                category[i] = crumb.strip()

        next_page = response.css("a[rel=next]::attr(href)").get()
        if next_page:
            yield self.follow_once(
                response,
                update_limit_qs(next_page),
                self.parse_grid, cb_kwargs={
                    'category': category
                })

        brand_filters = [
            brand.strip() for brand in response.css(
                '.default-brand-filters button::text').extract()
            if brand.strip() not in self.brands]

        for brand in brand_filters:
            self.brands.add(brand)

        brand_filters.extend(self.brand_cache.values())

        for box in response.css(".product-box"):
            product_url = box.css('.product-title-grid::attr(href)').get()
            cache_hit = self.brand_cache.get(
                box.css('.product-logo img::attr(src)').get())
            yield self.follow_once(
                response,
                product_url,
                self.parse_product,
                cb_kwargs={
                    'category': category,
                    'brand': cache_hit if cache_hit else self.match_brand(
                        box.css('.product-title-grid::text').get()),
                })

    def parse_product(self, response, category, brand):
        if response.css('h3 > i'):
            self.log("PRODUCT DOES NOT EXIST <{}>".format(
                response.request.url), logging.WARNING)
            return

        details = response.css('.produc-details-short')
        product_id = response.css('input[name=product_id]::attr(value)').get()

        # XXX: This site does not have pagination for product reviews.
        yield {
            'type': 'review',
            'collection': [{
                'product_id': product_id,
                'rating': len(comment.css('.fa-star')),
                'username': comment.css('p > span::text').get().strip(),
                'comment': (comment.css(
                    'p:last-child::text').get() or '').strip(),
            } for comment in response.css('.comments')]
        }

        specs = {}
        for tr in response.css('.information')[0].css('tr'):
            specs[tr.css('td:first-child::text').get().strip()] = \
                tr.css('td:last-child::text').get().strip()

        yield {
            'id': product_id,
            'title': details.css(".title::text").get().strip(),
            'category': category[0],
            'subcategory1': category[1],
            'subcategory2': category[2],
            'brand': brand,
            'price': (details.css('.price::text').get() or '0').strip(),
            'price_regular': (details.css(
                '.old-price::text').get() or '0').strip(),
            'specifications': specs,
            'code': details.css("p > span::text").get().strip(),
            'url': response.request.url,
        }
