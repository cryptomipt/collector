#!/usr/bin/env python2
# -*- coding: utf-8 -*-
from json import loads
from datetime import datetime
import settings
import logging
import requests
import utils
import ccxt.async as ccxt
import asyncio
from time import sleep

class ExchangeHarness(object):

    pairs = {
        'usd': ['btc', 'bch', 'eth', 'iota', 'xrp', 'xmr', 'omg', 'neo', 'eos', 'qtum', 'waves'],
        'btc': ['bch', 'eth', 'xrp', 'neo']
    }

    def __init__(self, exchange_id):
        self.exchange = getattr(ccxt, exchange_id)({ 'timeout': 10000 })

        loop = asyncio.get_event_loop()
        markets = loop.run_until_complete(self.exchange.load_markets())

        self.symbols = {}

        logging.info('Loaded markets for {}'.format(self.exchange.id))

        for symbol in markets:
            done = False
            for base in ExchangeHarness.pairs:
                for quote in ExchangeHarness.pairs[base]:
                    if (base in symbol and quote in symbol) or \
                            (base.upper() in symbol and quote.upper() in symbol):
                        if not '.' in symbol:
                            self.symbols[symbol] = '{}{}'.format(base.lower(), quote.lower())
                            done = True
                            break
                if done:
                    break

        logging.info('Symbols for {}: {}'.format(self.exchange.id, self.symbols))

        self.products = {}

        for symbol in self.symbols:
            self.products[symbol] = {
                'ticker': '{pairname}.{exchange}.ticker'.format(pairname=self.symbols[symbol],
                                                                exchange=self.exchange.id),
                'orderbook': '{pairname}.{exchange}.orderbook'.format(pairname=self.symbols[symbol],
                                                                      exchange=self.exchange.id)
            }

        logging.info('Indices for {}: {}'.format(self.exchange.id, self.products))

        self.time_between_requests = 0.1
        # self.markets = self.exchange.load_markets()

    def clean_ticker(self,data):
        clean_data = dict()
        now = datetime.utcnow()
        clean_data['tracker_time'] = now
        clean_data["ask"] = float(data["ask"])
        clean_data["bid"] = float(data["bid"])
        clean_data["price"] = float(data["last"])
        clean_data["exchange"] = self.exchange.id
        clean_data["product"] = data['symbol']
        clean_data['info'] = data['info']
        clean_data["size"] = float(data['baseVolume'])
        clean_data["volume"] = float(data['quoteVolume'])
        clean_data['time'] = data['timestamp']
        for k,v in data.items():
            if k not in clean_data.keys():
                clean_data[k]=v
        # if not clean_data["last"]:
        #     clean_data['last'] =
        return clean_data

    async def wait_and_send(self, time_to_wait, queue, msg):
        await asyncio.sleep(time_to_wait)
        await queue.put(msg)

    async def get_ticker(self, symbol, es):
        try:
            logging.debug('Send {} ticker request to {}'.format(self.symbols[symbol], self.exchange.id))
            ticker = await self.exchange.fetch_ticker(symbol)
        except Exception as e:
            logging.warning(str(e))
            return
        logging.debug('Got ticker {} from {}'.format(self.symbols[symbol], self.exchange.id))
        clean = self.clean_ticker(ticker)
        await self.on_ticker_received(symbol, clean, es)

    async def get_orderbook(self, symbol, es):
        try:
            logging.debug('Send {} orderbook request to {}'.format(self.symbols[symbol], self.exchange.id))
            orderbook = await self.exchange.fetch_order_book(symbol, {'depth': 10})
        except Exception as e:
            logging.warning(str(e))
            return
        logging.debug('Got orderbook {} from {}'.format(self.symbols[symbol], self.exchange.id))
        now = datetime.utcnow()
        orderbook['tracker_time'] = now
        await self.on_orderbook_received(symbol, orderbook, es)

    async def on_ticker_received(self, symbol, ticker, es):
        try:
            logging.debug(ticker)
            es.create(index=self.products[symbol]['ticker'], id=utils.generate_nonce(),
                      doc_type='ticker', body=ticker)
        except Exception as e:
            logging.warning('{}:{}'.format(str(e), ticker))
            # raise ValueError("Misformed Body for Elastic Search on " + self.exchange.id)

    async def on_orderbook_received(self, symbol, orderbook, es):
        try:
            logging.debug(orderbook)
            es.create(index=self.products[symbol]['orderbook'], id=utils.generate_nonce(),
                      doc_type='orderbook', body=orderbook)
        except Exception as e:
            logging.warning('{}:{}'.format(str(e), orderbook))
            # raise ValueError("Misformed Body for Elastic Search on " + self.exchange.id)


    async def record_data(self, es):
        """Record current tick"""
        while True:
            for product in self.products:
                asyncio.ensure_future(self.get_ticker(product, es))
                await asyncio.sleep(self.time_between_requests)
                asyncio.ensure_future(self.get_orderbook(product, es))
                await asyncio.sleep(self.time_between_requests)

            logging.info('All parameters retreived from {}'.format(self.exchange.id))