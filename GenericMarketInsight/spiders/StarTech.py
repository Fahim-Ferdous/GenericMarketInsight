# -*- coding: utf-8 -*-
import logging
from urllib.parse import urljoin

import lxml
import scrapy

from GenericMarketInsight.utils import update_url_query


def update_limit_qs(link, limit=90):
    return update_url_query(link, {'limit': limit})


def extract_locations(xml):
    et = lxml.etree.fromstring(xml)
    for location in et.xpath(
            './n:url/n:loc/text()', namespaces={'n': et.nsmap[None]}):
        yield location


class StartechSpider(scrapy.Spider):
    # NOTE: Star Tech's sitemap is unmaintained,
    # hence scrapy.Spider is inherited.
    # TODO: Parse offers.
    name = 'StarTech'
    allowed_domains = ['www.startech.com.bd']
    start_urls = ['https://www.startech.com.bd/']
    visited = set()
    product_ids = set()

    # NOTE: Let's not use update_limit_qs, it makes caching a nightmare.
    def follow_once(self, response, url, *args, **kwargs):
        url = url.lower().strip()
        if url not in self.visited:
            self.visited.add(url)
            return response.follow(url, *args, **kwargs)
        return None

    def parse_sitemap_location(self, response):
        if response.css('div.price-wrap > ins'):
            return self.parse_product(response)

        return self.parse_grid(response)

    def parse_sitemap(self, response):
        self.log("Evaluating sitemap", logging.INFO)
        for location in extract_locations(response.body):
            yield self.follow_once(
                response, location,
                self.parse_sitemap_location)

    def parse(self, response):
        if getattr(self, 'noincremental', 'yes').lower() in \
                ['yes', 'y', 't', 'true']:
            self.log("Crawling behaviour enabled.", logging.INFO)
            self.visited.add(response.request.url)
            for anchor in response.css(' '.join(
                    ['ul.responsive-menu',
                     'a:not([class=see-all])::attr(href)'])).extract():
                yield self.follow_once(response, anchor, self.parse_grid)
            yield response.follow('/sitemap.xml', self.parse_sitemap)
        else:
            self.log(
                'Incremental behaviour enabled. Can take a long time.',
                logging.WARNING)
            start = getattr(self, 'id_start', 0)
            upto = getattr(self, 'id_limit', 13020)
            base_url = urljoin(
                self.start_urls[0], 'product/product') + '?product_id='
            for i in range(start, upto):
                yield response.follow(
                    base_url + str(i), self.parse_product)

    def parse_grid(self, response):
        for anchor in response.css('h4.product-name a::attr(href)').extract():
            yield self.follow_once(response, anchor, self.parse_product)

        next_page = response.css(
            'ul.pagination li:last-child a::attr(href)').get()
        if next_page:
            yield self.follow_once(
                response, next_page, self.parse_grid)

    def parse_product_question(self, response, product_id):
        yield {
            'type': 'question',
            'collection': [{
                'product_id': product_id,
                'username': question.css('h5.question::text').get().strip(),
                'question': (
                        question.css('h6.questioner::text').get() or '').strip(),
                'answer': (
                        question.css('p.answer::text').get() or '').strip(),
            } for question in response.css('.question-wrap')]
        }

        yield from response.follow_all(
            css='li:last-child a::attr(href)',
            callback=self.parse_product_question,
            cb_kwargs={
                'product_id': product_id,
            })

    def parse_product_reviews(self, response, product_id):
        yield {
            'type': 'review',
            'collection': [{
                'product_id': product_id,
                'rating': len(comment.css('.fa-star')),
                'username': comment.css('h6.answerer::text').get().strip(),
                'comment': (comment.css('p.answer::text').get() or '').strip(),
            } for comment in response.css('.review-wrap')]
        }

        yield from response.follow_all(
            css='li:last-child a::attr(href)',
            callback=self.parse_product_reviews,
            cb_kwargs={
                'product_id': product_id,
            })

    def parse_product(self, response):
        product_id = response.css('.product-code::text').get()
        if product_id in self.product_ids:
            return
        self.product_ids.add(product_id)

        if response.css('#write-review > h3::text') != 'Reviews (0) :':
            yield response.follow(
                '/product/product/review?product_id=%s' % product_id,
                self.parse_product_reviews, cb_kwargs={
                    'product_id': product_id,
                })
        yield response.follow(
            '/product/product/question?product_id=%s' % product_id,
            self.parse_product_question, cb_kwargs={
                'product_id': product_id,
            })

        title = response.css('h1.product-name::text').get()
        categoricals = [None, None, None]
        breadcrumbs = response.css('ul.breadcrumb span::text').extract()[:-1]
        for i, crumb in enumerate(breadcrumbs):
            if i >= len(categoricals):
                if breadcrumbs[i].lower() != breadcrumbs[i - 1].lower():
                    self.log("Item <{}> has {} categoricals {}".format(
                        title, len(breadcrumbs), breadcrumbs), logging.WARNING)
                break
            categoricals[i] = crumb.strip()

        specs = {}
        for table_row in response.css('.data-table tbody tr'):
            specs[table_row.css('td:first-child::text').get().strip()] = \
                table_row.css('td:last-child::text').get().strip()

        price = response.css('.product-price::text').get()[:-1]
        if not price.strip():
            price = response.css('.product-price ins ::text').get()[:-1]
        price_regular = response.css('.product-regular-price::text').get()
        if price_regular:
            price_regular = price_regular[:-1]
        else:
            price_regular = price

        yield {
            'id': product_id,
            'title': title,
            'category': categoricals[0],
            'subcategory1': categoricals[1],
            'subcategory2': categoricals[2],
            'brand': response.css('.product-brand::text').get(),
            'price_regular': price_regular,
            'price': price,
            'specifications': specs,
            'status': response.css('div.price-wrap > ins::text').get(),
            'url': response.request.url,
        }
