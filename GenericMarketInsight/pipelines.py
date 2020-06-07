# -*- coding: utf-8 -*-

# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


from urllib.parse import urlparse

from scrapy.exceptions import DropItem

import models


class PreProcessor:
    id_prefix = ''

    def __init__(self):
        pass

    def preprocess_product(self, product):
        product['id'] = self.id_prefix + product['id']
        product['price_regular'] = int(
            product['price_regular'].replace(',', ''))
        product['price'] = int(product['price'].replace(',', ''))
        product['url'] = urlparse(product['url']).path

        return product

    def fix_prefix_collection(self, collection, key='product_id'):
        """Prepend `id_prefix' to collection's element's value for `key'"""
        for idx in range(len(collection)):
            collection[idx][key] = self.id_prefix + collection[idx][key]
        return collection


class StarTechPreProcessor(PreProcessor):
    id_prefix = 'stech'

    def __init__(self):
        super(StarTechPreProcessor, self).__init__()

    def preprocess_product(self, product):
        if product['status'].endswith('৳'):
            product['status'] = 'Available'
        product['code'] = product['id']
        return super().preprocess_product(product)


class RyansComputersPreProcessor(PreProcessor):
    id_prefix = 'ryans'

    def __init__(self):
        super(RyansComputersPreProcessor, self).__init__()

    def preprocess_product(self, product):
        product['status'] = 'Available'
        return super().preprocess_product(product)


class Pipeline:
    db = None
    ninstances = 0
    brands = {}

    def __init__(self):
        self.item_set = set()
        self.brand_corrections = {
            'a data': 'ADATA',
            'a4 tech': 'A4TECH',
            'jbl': 'JBL by Harman',
        }

        self.platform = None

        self.preprocessor = None
        Pipeline.ninstances += 1

    def open_spider(self, spider):
        if not Pipeline.db:
            Pipeline.db = models.create_db_session(
                getattr(spider, 'dburi', models.DEFAULT_DBURI))

        Pipeline.brands = {
            i.title.lower(): i for i in Pipeline.db.query(models.Brand).all()}

        self.item_set = set(
            i[0] for i in Pipeline.db.query(models.Product.id).all())

        if spider.name == 'RyansComputers':
            self.preprocessor = RyansComputersPreProcessor()
        elif spider.name == 'StarTech':
            self.preprocessor = StarTechPreProcessor()

        if len(spider.start_urls) > 1:
            spider.log('. '.join([
                "Should have only one start URL",
                "Have {} URLs",
                "Picking up the <{}> as the main platform URL"]).format(
                len(spider.start_urls)), spider.start_urls[0])
        # Get or set the Platform object.
        platform_url = urlparse(spider.start_urls[0]).netloc
        platform_title = spider.platform_title

        self.platform = Pipeline.db.query(models.Platform). \
            filter(models.Platform.title == platform_title). \
            filter(models.Platform.url == platform_url).first()
        if not self.platform:
            self.platform = models.Platform(title=platform_title, url=platform_url)
            Pipeline.db.add(self.platform)

    def close_spider(self, _):
        Pipeline.ninstances -= 1
        if Pipeline.ninstances == 0:
            Pipeline.db.commit()
            Pipeline.db.close()

    def process_collection(self, item, cls):
        Pipeline.db.add_all([
            cls(**item) for item in
            self.preprocessor.fix_prefix_collection(
                item['collection'])])
        return item

    def process_item(self, item, _):
        if 'price_regular' in item:
            return self.process_product(item)
        if 'collection' in item:
            if item['type'] == 'review':
                return self.process_collection(item, models.Review)
            if item['type'] == 'question':
                return self.process_collection(item, models.Question)

        raise DropItem("NotImplemented")

    def get_set_brand(self, name):
        """
            Step 1: Check if name is None or not.
            Step 2: Set name to lower(name), for ease of caching.
            Step 3: If name is in correction, set name to lower(correct name).
            Step 4: If name brands is in cache, get the cached Brand object.
            Step 5: Else, create a Brand object with title = original name
                    (correct but not lower cased). Then store it into the
                    cache it with name (correct and lower cased) as the key.
            Step 6: Return the Brand object.
        """
        if not name:
            return None

        name_original = name
        name = name_original.lower()
        if name in self.brand_corrections:
            name_original = self.brand_corrections[name]
            name = name_original.lower()

        if name in Pipeline.brands:
            return Pipeline.brands[name]

        brand = models.Brand(title=name_original)

        Pipeline.brands[name] = brand
        Pipeline.db.add(brand)

        return brand

    def process_product(self, item):
        item = self.preprocessor.preprocess_product(item)

        if item['id'] in self.item_set:
            raise DropItem("Duplicate product")

        self.item_set.add(item['id'])

        db_item = item.copy()

        status = db_item['status']
        if status == 'Available':
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
            raise DropItem("Item {} has unknown status {}".format(db_item['id'], status))

        db_item['brand'] = self.get_set_brand(item['brand'])

        db_item['platform'] = self.platform

        db_item['specifications'] = [
            models.Specification(key=spec[0], value=spec[1])
            for spec in item['specifications'].items()
        ]

        Pipeline.db.add(models.Product(**db_item))

        return item
