#!/usr/bin/env python3
import os
import os.path
import dotenv
import ccxt.async as ccxt
import asyncio


def main() -> int:
    dotenv_path = os.path.join(os.path.dirname(__file__), '../.env')
    dotenv.load_dotenv(dotenv_path)
    cs = ['XRP', 'JPY', 'BTC']
    hitbtc2 = ccxt.hitbtc2({
        'apiKey': os.environ.get('hitbtc2_key'),
        'secret': os.environ.get('hitbtc2_secret')})
    bitbank = ccxt.bitbank({
        'apiKey': os.environ.get('bitbank_key'),
        'secret': os.environ.get('bitbank_secret')})
    bitflyer = ccxt.bitflyer({
        'apiKey': os.environ.get('bitflyer_key'),
        'secret': os.environ.get('bitflyer_secret')})
    ts = [hitbtc2, bitbank, bitflyer]
    el = asyncio.get_event_loop()
    bs = el.run_until_complete(
        asyncio.gather(*[t.fetch_balance() for t in ts]))
    cbs = [sum([b['total'].get(c, 0) for b in bs]) for c in cs]
    lightning = el.run_until_complete(bitflyer.fetch2(
        path='getcollateral', api='private', method='GET'))
    val = el.run_until_complete(asyncio.gather(
        bitbank.fetch_order_book('XRP/JPY', limit=1),
        bitbank.fetch_order_book('BTC/JPY', limit=1)))
    el.run_until_complete(asyncio.gather(*[t.close() for t in ts]))
    added = [
        cbs[0],
        cbs[1] + lightning['collateral'] + lightning['open_position_pnl'],
        cbs[2]]
    p = (
        added[0] * val[0]['bids'][0][0] +
        added[1] +
        added[2] * val[1]['bids'][0][0])
    print(p)
    return 0


if __name__ == "__main__":
    exit(main())

# vim:fenc=utf-8 ff=unix ft=python ts=4 sw=4 sts=4 fdm=indent fdl=0 fdn=1:
# vim: si et cinw=if,elif,else,for,while,try,except,finally,def,class:
