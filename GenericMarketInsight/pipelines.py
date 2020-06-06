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

        self.item_url = {}

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

    def process_reviews(self, item, _):
        self.db.add_all([
            models.Review(**item) for item in
            item['collection_review']])

        return item

    def process_questions(self, item, spider):
        # raise DropItem("NotImplemented(collection_question)")
        return item

    def process_item(self, item, spider):
        if 'price_regular' in item:
            return self.process_product(item)
        if 'brand_name' in item:
            return self.process_brand(item)
        if 'collection_review' in item:
            return self.process_reviews(item, spider)
        if 'collection_question' in item:
            return self.process_questions(item, spider)

        raise DropItem("NotImplemented")

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
            raise DropItem("Duplicate product")

        self.item_set.add(item['id'])
        self.item_url[item['id']] = item['url']

        item['price_regular'] = int(item['price_regular'].replace(',', ''))
        item['price'] = int(item['price'].replace(',', ''))

        brand = self.brand_corrections.get(item['brand'], item['brand'])
        if not self.brands.get(brand):
            brand_item = models.Brand(title=brand)
            self.brands[brand] = brand_item

        db_item = item.copy()
        status = db_item['status']
        if status.endswith('৳'):
            db_item['status'] = models.ItemStatusEnum.AVAILABLE
        elif status == "Out Of Stock":
            db_item['status'] = models.ItemStatusEnum.OUTOFSTOCK
        elif status == "Discontinued":
            db_item['status'] = models.ItemStatusEnum.DISCONTINUED
        elif status == "Pre Order":
            db_item['status'] = models.ItemStatusEnum.PREORDER
        elif status == "Up Coming":
            db_item['status'] = models.ItemStatusEnum.UPCOMING
        elif status == "Call for Price":
            db_item['status'] = models.ItemStatusEnum.CALLFORPRICE
        else:
            # TODO: modify logger's dropped method to be more user friendly.
            raise DropItem("Item {} has unknown status {}".format(
                db_item['id'], status))

        db_item['brand'] = self.brands[brand]

        # db_item['reviews'] = [
        #     models.Review(**review) for review in item['reviews']
        # ]

        db_item['specifications'] = [
            models.Specification(key=spec[0], value=spec[1])
            for spec in item['specifications'].items()
        ]

        self.db.add(models.Product(**db_item))
        self.load_count += 1

        return item
