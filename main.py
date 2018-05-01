#!/usr/bin/env python3
"""auto arbitrage."""
import os
import os.path
import dotenv
import ccxt.async as ccxt
import time
import asyncio
import numpy as np
from traceback import print_exc
from functools import reduce


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
    el = asyncio.get_event_loop()
    (hitbtc2Markets, bitbankMarkets) = el.run_until_complete(asyncio.gather(
        hitbtc2.load_markets(),
        bitbank.load_markets()))
    minUnit = {
        'bitbank': {
            'XRP/JPY': 0.0001,
            'BTC/JPY': 0.0001},
        'hitbtc2': {
            'XRP/BTC': hitbtc2Markets['XRP/BTC']['limits']['amount']['min']}}
    return {'hitbtc2': hitbtc2, 'bitbank': bitbank, 'minUnit': minUnit}


def attemptTrade(inited, capacity, value):
    """判断 トレード 余力取得."""
    production = False
    try:
        hitbtc2 = {
            'asks': np.array(value['hitbtc2']['XRP/BTC']['asks']),
            'bids': np.array(value['hitbtc2']['XRP/BTC']['bids'])}
        bitbankXrp = {
            'asks': np.array(value['bitbank']['XRP/JPY']['asks']),
            'bids': np.array(value['bitbank']['XRP/JPY']['bids'])}
        bitbankBtc = {
            'asks': np.array(value['bitbank']['BTC/JPY']['asks']),
            'bids': np.array(value['bitbank']['BTC/JPY']['bids'])}

        depth = min([
            min(len(x['asks']), len(x['bids']))
            for x in [hitbtc2, bitbankXrp, bitbankBtc]])

        # hitbtc2のXRP/BTCとbitbankのXRP/BTC(XRP/JPY / BTC/JPY)
        # 閾値を越える取引可能量を板から推測する

        #cum_down1 = np.vstack([np.cumsum(depth1["asks"][:, 1][:n_depth]), np.zeros(n_depth)])
        #cum_down2 = np.vstack([np.cumsum(depth2["bids"][:, 1][:n_depth]), np.ones(n_depth)])
        #cum_down = np.hstack((cum_down1, cum_down2))
        #sorder_down = cum_down[1][np.argsort(cum_down[0])][:n_depth]
        #print(sorder_down)

        #cum_up1 = np.vstack([np.cumsum(depth1["bids"][:, 1][:n_depth]), np.ones(n_depth)])
        #cum_up2 = np.vstack([np.cumsum(depth2["asks"][:, 1][:n_depth]), np.zeros(n_depth)]) # (2, depth)
        #cum_up = np.hstack((cum_up1, cum_up2)) # (2, depth * 2)
        #sorder_up = cum_up[1][np.argsort(cum_up[0])][:n_depth] # (depth,) 価格順でbidかaskかのフラグ
        #print(sorder_up)

        ## 注文額の比率が インデックスで対応するの???
        #i1, i2 = 0, 0
        #ratelist_up = np.zeros((n_depth,2))
        #for si in range(n_depth):
        #    so = sorder_up[si]
        #    if so == 0:
        #        ratelist_up[si] = depth1["bids"][i1][0]/depth2["asks"][i2][0], cum_up2[0][i2]
        #        i2 +=1
        #    if so == 1:
        #        ratelist_up[si] = depth1["bids"][i1][0]/depth2["asks"][i2][0], cum_up1[0][i1]
        #        i1 +=1
        #print(ratelist_up)

        #i1, i2= 0, 0
        #ratelist_down = np.zeros((n_depth,2))
        #for si in range(n_depth):
        #    so = sorder_down[si]
        #    if so == 0:
        #        ratelist_down[si] = depth2["bids"][i2][0]/depth1["asks"][i1][0], cum_down1[0][i1]
        #        i1 +=1
        #    if so == 1:
        #        ratelist_down[si] = depth2["bids"][i2][0]/depth1["asks"][i1][0], cum_down2[0][i2]
        #        i2 +=1
        #print(ratelist_down)
        #u_idx = np.sum(ratelist_up[:, 0] >= thrd_up) # しきい値を超えたrateの個数
        #d_idx = np.sum(ratelist_down[:, 0] >= thrd_down)

        #tradeflag = np.sign(u_idx) - np.sign(d_idx)

        #if (depth1["asks"][0][0] < depth1["bids"][0][0]):
        #    tradeflag = 0
        #    print("invalid orderbook in {}, ask={}, bid={}".format(self.t1.name, depth1["asks"][0][0], depth1["bids"][0][0]))
        #if (depth2["asks"][0][0] < depth2["bids"][0][0]):
        #    tradeflag = 0
        #    print("invalid orderbook in {}, ask={}, bid={}".format(self.t2.name, depth2["asks"][0][0], depth2["bids"][0][0]))

        #if tradeflag == 0:
        #    tradable_value = 0
        #if tradeflag == 1:
        #    tradable_value = ratelist_up[u_idx -1][1]
        #if tradeflag == -1:
        #    tradable_value = ratelist_down[d_idx -1][1]

        doTrade = False
        if doTrade:
            print('trade')
            if production:
                # order
                pass
            return fetchCapacity(inited)
        else:
            return capacity
    except Exception:
        print_exc()
    return fetchCapacity(inited)


def fetchCapacity(inited):
    """余力取得."""
    el = asyncio.get_event_loop()
    cap = el.run_until_complete(asyncio.gather(
        inited['hitbtc2'].fetch_balance(),
        inited['bitbank'].fetch_balance()))
    newCap = {'hitbtc2': cap[0]['free'], 'bitbank': cap[1]['free']}
    return newCap


def fetchValue(inited):
    """価格と売買可能量取得."""
    def f(dic, ident, symbol):
        return dic[ident].fetch_order_book(symbol)
    el = asyncio.get_event_loop()
    val = el.run_until_complete(asyncio.gather(
        inited['hitbtc2'].fetch_order_book('XRP/BTC', limit=20),
        inited['bitbank'].fetch_order_book('XRP/JPY', limit=20),
        inited['bitbank'].fetch_order_book('BTC/JPY', limit=20)))
    newVal = {
        'hitbtc2': {'XRP/BTC': val[0]},
        'bitbank': {'XRP/JPY': val[1], 'BTC/JPY': val[2]}}
    return newVal


if __name__ == "__main__":
    exit(main())

# vim:fenc=utf-8 ff=unix ft=python ts=4 sw=4 sts=4 fdm=indent fdl=0 fdn=1:
# vim: si et cinw=if,elif,else,for,while,try,except,finally,def,class:
