#!/usr/bin/env python3
"""auto arbitrage."""
import os
import os.path
import dotenv
import ccxt
import time
import asyncio


def main() -> int:
    """main."""
    inited = init()
    capacity = None
    while True:
        try:
            # bitbank ETH JP
            # hitbtc ETH BTC(bitbankのBTC/JPで換算)
            value = fetchValue(inited)
            capacity = attemptTrade(inited, capacity, value)
            time.sleep(3)
        except Exception:
            from traceback import print_exc
            print_exc()
            time.sleep(10)
    return 0


def init():
    """apiなど初期化."""
    dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
    dotenv.load_dotenv(dotenv_path)
    hitbtc2 = ccxt.hitbtc2({
        'apiKey': os.environ.get('hitbtc2_key'),
        'secret': os.environ.get('hitbtc2_secret')})
    bitbank = ccxt.bitbank({
        'apiKey': os.environ.get('bitbank_key'),
        'secret': os.environ.get('bitbank_secret')})
    return {'hitbtc2': hitbtc2, 'bitbank': bitbank}


def attemptTrade(inited, capacity, value):
    """判断 トレード 余力取得."""
    try:
        production = False
        print(value)
        doTrade = False
        if doTrade:
            print('trade')
            if production:
                # order
                pass
    except Exception:
        pass
    updateCap = capacity is None or doTrade
    if updateCap:
        el = asyncio.get_event_loop()
        cap = el.run_until_complete(asyncio.gather(
            el.run_in_executor(None, fetchCapacity, inited, 'hitbtc2'),
            el.run_in_executor(None, fetchCapacity, inited, 'bitbank')))
        newCap = {'hitbtc2': cap[0], 'bitbank': cap[1]}
        print(newCap)
        return newCap
    else:
        return capacity


def fetchCapacity(dic, ident):
    """余力取得."""
    return dic[ident].fetch_balance()['free']


def fetchValue(inited):
    """価格取得."""
    def f(dic, ident, symbol):
        return dic[ident].fetch_order_book(symbol)
    el = asyncio.get_event_loop()
    val = el.run_until_complete(asyncio.gather(
        el.run_in_executor(None, f, inited, 'hitbtc2', 'XRP/BTC'),
        el.run_in_executor(None, f, inited, 'bitbank', 'XRP/JPY'),
        el.run_in_executor(None, f, inited, 'bitbank', 'BTC/JPY')))
    newVal = {
        'hitbtc2': {'XRP/BTC': val[0]},
        'bitbank': {'XRP/JPY': val[1], 'BTC/JPY': val[2]}}
    return newVal


if __name__ == "__main__":
    exit(main())

# vim:fenc=utf-8 ff=unix ft=python ts=4 sw=4 sts=4 fdm=indent fdl=0 fdn=1:
# vim: si et cinw=if,elif,else,for,while,try,except,finally,def,class:
