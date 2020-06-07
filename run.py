from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

from GenericMarketInsight.spiders.RyansComputers import RyanscomputersSpider
from GenericMarketInsight.spiders.StarTech import StartechSpider


def run():
    settings = get_project_settings()
    crawler = CrawlerProcess(settings)
    crawler.crawl(RyanscomputersSpider)
    crawler.crawl(StartechSpider)
    crawler.start()
    crawler.join()


if __name__ == '__main__':
    run()
