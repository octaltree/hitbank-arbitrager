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


def main() -> int:
    """main."""
    production = bool(os.environ.get('production_arbitrager', False))
    print('mode: ' + ('production' if production else 'dry run'))
    inited = init()
    capacity = fetchCapacity(inited)
    printCapacity(capacity)
    while True:
        try:
            # bitbank ETH JP
            # hitbtc ETH BTC(bitbankのBTC/JPで換算)
            value = fetchValue(inited)
            print('評価額{}円'.format(calcMoney(capacity, value)))
            newCap = attemptTrade(
                inited, capacity, value,
                production=production)
            if newCap != capacity:
                printCapacity(newCap)
                capacity = newCap
            time.sleep(4)
        except Exception as e:
            print_exc()
            print(e)
            return 1
            time.sleep(5)
            capacity = fetchCapacity(inited)
            printCapacity(capacity)
    return 0


def printCapacity(capacity):
    """資産を表示."""
    print('資産 {}XRP {}JPY {}BTC'.format(
        capacity['bitbank']['XRP'] + capacity['hitbtc2']['XRP'],
        capacity['bitbank']['JPY'],
        capacity['bitbank']['BTC'] + capacity['hitbtc2']['BTC']))


def calcMoney(capacity, value):
    """評価額XRP換算."""
    xrp = value['bitbank']['XRP/JPY']['bids'][0][0]
    btc = value['bitbank']['BTC/JPY']['bids'][0][0]
    res = (
        capacity['bitbank']['JPY'] +
        (capacity['bitbank']['XRP'] + capacity['hitbtc2']['XRP']) * xrp +
        (capacity['bitbank']['BTC'] + capacity['hitbtc2']['BTC']) * btc)
    return res


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
    bitbank2 = ccxt.bitbank({
        'apiKey': os.environ.get('bitbank_key2'),
        'secret': os.environ.get('bitbank_secret2')})
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
    return {'hitbtc2': hitbtc2, 'bitbank': bitbank,
            'bitbank2': bitbank2, 'minUnit': minUnit}


def attemptTrade(inited, capacity, value, production=False):
    """判断 トレード 余力取得."""
    hitbtc2 = {
        'asks': np.array(value['hitbtc2']['XRP/BTC']['asks'][:10]),
        'bids': np.array(value['hitbtc2']['XRP/BTC']['bids'][:10])}
    bitbankXrp = {
        'asks': np.array(value['bitbank']['XRP/JPY']['asks'][:10]),
        'bids': np.array(value['bitbank']['XRP/JPY']['bids'][:10])}
    bitbankJpy = {  # JPY/BTC (JPY1円あたりのBTC枚数, 円)
        'asks': np.array([
            [1 / x[0], x[1] * x[0]]
            for x in value['bitbank']['BTC/JPY']['bids'][:10]]),
        'bids': np.array([
            [1 / x[0], x[1] * x[0]]
            for x in value['bitbank']['BTC/JPY']['asks'][:10]])}

    # XRPの枚数で取引量を示す
    # 1: BASE2/BASE1, 2: ALT/BASE2, 3: ALT/BASE1
    # 1: JPY/BTC, 2: XRP/JPY, 3: XRP/BTC
    thresholdS = 1.005
    thresholdB = 1.005
    (ratioS, valS, pbjS, pbxS, phxS) = calcSellingTwice(
        bitbankJpy['bids'],
        bitbankXrp['bids'],
        hitbtc2['asks'], thresholdS)
    (ratioB, valB, pbjB, pbxB, phxB) = calcBuyingTwice(
        bitbankJpy['asks'],
        bitbankXrp['asks'],
        hitbtc2['bids'], thresholdB)
    print((ratioS, valS, ratioB, valB))
    doTrade = (
        1 if ratioS >= thresholdS else  # 2回売る
        -1 if ratioB >= thresholdB else  # 2回買う
        0)
    if not doTrade:
        return capacity

    # 指値価格
    ratio = ratioS if doTrade == 1 else ratioB
    pbj = pbjS if doTrade == 1 else pbjB  # pbj BTC per JPY in bitbank
    pbb = 1 / pbj  # pbb JPY per BTC
    pbx = pbxS if doTrade == 1 else pbxB  # pbx JPY per XRP
    phx = phxS if doTrade == 1 else phxB  # phx BTC per XRP in hitbtc
    # TODO 円の増減があり働いてない
    minUnit = max([
        inited['minUnit']['bitbank']['BTC/JPY'] / pbj / pbx,
        inited['minUnit']['hitbtc2']['XRP/BTC'],
        inited['minUnit']['bitbank']['XRP/JPY']])
    capS = min([
        capacity['bitbank']['XRP'],
        capacity['bitbank']['JPY'] / pbx,
        capacity['hitbtc2']['BTC'] / pbj / pbx])
    capB = min([
        capacity['bitbank']['JPY'] / pbx,
        capacity['bitbank']['BTC'] / pbj / pbx,
        capacity['hitbtc2']['XRP']])
    cap = capS if doTrade == 1 else capB
    val = min([cap * 0.8, valS if doTrade == 1 else valB])
    vb = val * pbx * pbj
    print('  tradeChance {}XRP'.format(val))
    print('    {}XRP単位で取引可'.format(minUnit))
    print('    1JPYを{}BTCで{}'.format(pbj, '売' if doTrade == 1 else '買'))
    print('      すなわち1BTCを{}JPYで{}'.format(
        pbb, '買' if doTrade == 1 else '売'))
    print('    1XRPを{}JPYで{}'.format(pbx, '売' if doTrade == 1 else '買'))
    print('    1XRPを{}BTCで{}'.format(phx, '買' if doTrade == 1 else '売'))
    print('    1XRPあたり{}BTC得 {}'.format(
        doTrade * (pbj * pbx - phx), ratio))
    if val < minUnit:
        print('  資産')
        print('    hitbtc {}XRP {}BTC={}XRP'.format(
            capacity['hitbtc2']['XRP'], capacity['hitbtc2']['BTC'],
            capacity['hitbtc2']['BTC'] / phx))
        print('    bitbank {}XRP {}JPY={}XRP {}BTC={}XRP'.format(
            capacity['bitbank']['XRP'], capacity['bitbank']['JPY'],
            capacity['bitbank']['JPY'] / pbx, capacity['bitbank']['BTC'],
            capacity['bitbank']['BTC'] / pbj / pbx))
        return capacity

    # TODO 売買量をいじって偏りをなおす
    if doTrade == 1:  # 2回売る
        print('sell bitbank XRP/JPY {}XRP {}JPY per XRP'.format(val, pbx))
        print('buy bitbank BTC/JPY {}BTC {}JPY per BTC'.format(vb, pbb))
        print('buy hitbtc2 XRP/BTC {}XRP'.format(val))
        if production:
            el = asyncio.get_event_loop()
            bx = inited['bitbank'].create_order(
                'XRP/JPY', 'market', 'sell', val, 9999999)
            bj = inited['bitbank2'].create_order(
                'BTC/JPY', 'market', 'buy', vb, 1)
            hx = inited['hitbtc2'].create_market_buy_order('XRP/BTC', val)
            res = el.run_until_complete(asyncio.gather(bx, bj, hx))
            print(res)
    elif doTrade == -1:  # 2回買う
        print('buy bitbank XRP/JPY {}XRP {}JPY per XRP'.format(val, pbx))
        print('sell bitbank BTC/JPY {}BTC {}JPY per BTC'.format(vb, pbb))
        print('sell hitbtc2 XRP/BTC {}XRP'.format(val))
        if production:
            el = asyncio.get_event_loop()
            bx = inited['bitbank'].create_order(
                'XRP/JPY', 'market', 'buy', val, 1)
            bj = inited['bitbank2'].create_order(
                'BTC/JPY', 'market', 'sell', vb, pbb)
            hx = inited['hitbtc2'].create_market_sell_order('XRP/BTC', val)
            res = el.run_until_complete(asyncio.gather(bx, bj, hx))
            print(res)
    return fetchCapacity(inited)


# 1: BASE2/BASE1, 2: ALT/BASE2, 3: ALT/BASE1
def calcBuyingTwice(ask1, ask2, bid3, threshold):
    """ALT -> BASE1がBASE1 -> BASE2 -> ALTを上回れば(比率, 量)を返す."""
    idx = np.zeros(3).astype(int)

    amount1 = np.cumsum(ask1[:, 1] / ask2[-1][0])
    amount2 = np.cumsum(ask2[:, 1])
    amount3 = np.cumsum(bid3[:, 1])

    ratio = bid3[:, 0][idx[2]] / (ask1[:, 0][idx[0]] * ask2[:, 0][idx[1]])
    if ratio < threshold:
        return (ratio, 0, 0, 0, 999999999999)
    value = np.min([amount1[idx[0]], amount2[idx[1]], amount3[idx[2]]])

    for i in range(9):
        idx[np.argmin([
            amount1[idx[0]], amount2[idx[1]], amount3[idx[2]]])] += 1
        new_ratio = (
            bid3[:, 0][idx[2]] / (ask1[:, 0][idx[0]] * ask2[:, 0][idx[1]]))
        if new_ratio < threshold:
            break
        ratio = new_ratio
        # value = np.min([amount1[idx[0]], amount2[idx[1]], amount3[idx[2]]])
    return (ratio, value, ask1[idx[0], 0], ask2[idx[1], 0], bid3[idx[2], 0])


def calcSellingTwice(bid1, bid2, ask3, threshold):
    """ALT -> BASE2 -> BASE1がBASE1 -> ALTを上回れば(比率, 量)を返す."""
    idx = np.zeros(3).astype(int)

    amount1 = np.cumsum(bid1[:, 1] / bid2[-1][0])
    amount2 = np.cumsum(bid2[:, 1])
    amount3 = np.cumsum(ask3[:, 1])

    ratio = bid1[:, 0][idx[0]] * bid2[:, 0][idx[1]] / ask3[:, 0][idx[2]]
    if ratio < threshold:
        return (ratio, 0, 99999999999, 9999999999, 0)
    value = np.min([amount1[idx[0]], amount2[idx[1]], amount3[idx[2]]])

    for i in range(9):
        idx[np.argmin([
            amount1[idx[0]], amount2[idx[1]], amount3[idx[2]]])] += 1
        new_ratio = (
            bid1[:, 0][idx[0]] * bid2[:, 0][idx[1]] / ask3[:, 0][idx[2]])
        if new_ratio < threshold:
            break
        ratio = new_ratio
        # value = np.min([amount1[idx[0]], amount2[idx[1]], amount3[idx[2]]])
    return (ratio, value, bid1[idx[0], 0], bid2[idx[1], 0], ask3[idx[2], 0])


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
        inited['hitbtc2'].fetch_order_book('XRP/BTC', limit=10),
        inited['bitbank'].fetch_order_book('XRP/JPY', limit=10),
        inited['bitbank'].fetch_order_book('BTC/JPY', limit=10)))
    newVal = {
        'hitbtc2': {'XRP/BTC': val[0]},
        'bitbank': {'XRP/JPY': val[1], 'BTC/JPY': val[2]}}
    return newVal


if __name__ == "__main__":
    exit(main())

# vim:fenc=utf-8 ff=unix ft=python ts=4 sw=4 sts=4 fdm=indent fdl=0 fdn=1:
# vim: si et cinw=if,elif,else,for,while,try,except,finally,def,class:
