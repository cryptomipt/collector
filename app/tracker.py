#!/usr/bin/env python2
# -*- coding: utf-8 -*-
from elasticsearch import Elasticsearch, helpers
from exchange_harness import ExchangeHarness
import logging
import functools
# import schedule
import asyncio
import settings
import utils
import random
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import ProcessPoolExecutor
from time import sleep

def main():
    logging.basicConfig(format='%(levelname)s:%(asctime)s %(message)s',level=settings.LOGLEVEL)
    es = Elasticsearch(settings.ELASTICSEARCH_CONNECT_STRING)

    logging.info('Market Refresh Rate: ' + str(settings.MARKET_REFRESH_RATE) + ' seconds.')
    logging.info('Initial Sleep: ' + str(5) + ' seconds.')

    # logging.info('Application Started.')
    # RESTful_exchanges = ['bittrex', 'kraken', 'poloniex', 'kucoin', 'cryptopia']
    RESTful_exchanges = ['bitmex']
    exchanges = [ExchangeHarness(x) for x in RESTful_exchanges]

    # print active exchanges and create indexes in kibana based on products listed in each market
    for exchange in exchanges:
        logging.info(exchange.exchange.id + ': activated and indexed.')
        for product, kibana_index in exchange.products.items():
            utils.create_index(es, kibana_index['ticker'])
            utils.create_index(es, kibana_index['orderbook'])

    logging.warning('Initiating Market Tracking.')

    #Record Ticks
    while True:
        loop = asyncio.get_event_loop()
        try:
            for exchange in exchanges:
                asyncio.ensure_future(exchange.record_data(es))
            loop.run_forever()
        except Exception as e:
            logging.warning(e)
        loop.close()



if __name__ == '__main__':

    main()
