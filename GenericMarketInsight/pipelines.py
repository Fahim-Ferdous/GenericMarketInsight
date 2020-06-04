# -*- coding: utf-8 -*-

# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


from copy import copy

from scrapy.exceptions import DropItem
from scrapy.utils.log import logger

import models


class GenericmarketinsightPipeline:
    def __init__(self):
        self.db = None
        self.item_set = set()
        self.brands = {}
        self.load_count = 0
        self.brand_corrections = {
            'A Data': 'ADATA',
            'A4 Tech': 'A4TECH',
            'JBL': 'JBL by Harman',
        }

    def open_spider(self, spider):
        self.db = models.create_db_session(
            getattr(spider, 'dburi', models.DEFAULT_DBURI))

        self.brands = {i.title: i for i in self.db.query(models.Brand).all()}

        self.item_set = set(
            i[0] for i in self.db.query(models.Product.id).all())

    def close_spider(self, _):
        self.db.commit()
        self.db.close()
        logger.info("Parsed %d products" % self.load_count)

    def process_item(self, item, _):
        if item.get('price'):
            return self.process_product(item)
        if item.get('brand_name'):
            return self.process_brand(item)

    def process_brand(self, item):
        name = item['brand_name']
        if name in self.brands:
            raise DropItem("Duplicate brand name %s" % name)

        if self.brand_corrections.get(name):
            correction = self.brand_corrections[name]
            brand = models.Brand(title=correction)
            self.brands[correction] = brand
            item['brand_name'] = correction
        else:
            brand = models.Brand(title=name)

        self.brands[name] = brand
        self.db.add(brand)

        return item

    def process_product(self, item):
        if item['id'] in self.item_set:
            raise DropItem("Duplicate product id %s" % item['id'])

        self.item_set.add(item['id'])

        item['price'] = int(item['price'].replace(',', ''))
        item['price_old'] = int(item['price_old'].replace(',', ''))

        db_item = item.copy()
        db_item['brand'] = db_item['brand'] and self.brands[
            self.brand_corrections.get(db_item['brand'], db_item['brand'])]

        db_item['reviews'] = [
            models.Review(**review) for review in item['reviews']
        ]

        db_item['specifications'] = [
            models.Specification(key=spec[0], value=spec[1])
            for spec in item['specifications'].items()
        ]

        self.db.add(models.Product(**db_item))
        self.load_count += 1

        return item
