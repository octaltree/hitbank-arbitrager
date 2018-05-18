#!/usr/bin/env python3
"""auto arbitrage."""
import os
import os.path
import dotenv
import ccxt.async as ccxt
import time
import asyncio
import numpy as np
import slackweb
import traceback
import datetime

slack = slackweb.Slack(
    url="https://hooks.slack.com/services" +
    "/T3BHKTNNM/BAM3F7LVA/GLLeXG3CC5qDxC2baFcYsUoP")


def log(s):
    """ログ出力."""
    print(s, flush=True)
    slack.notify(text=str(s))


def main() -> int:
    """main."""
    production = bool(os.environ.get('production_arbitrager', False))
    log('\n'.join([
        'mode: ' + ('production' if production else 'dry run'),
        datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")]))
    inited = init()
    capacity = None
    cooldown = 1
    while True:
        try:
            # bitbank ETH JP
            # hitbtc ETH BTC(bitbankのBTC/JPで換算)
            value = fetchValue(inited)
            if cooldown <= 0:
                traded = attemptTrade(
                    inited, capacity, value,
                    production=production)
                if traded:
                    cooldown = 4
                    log('@channel')
            newCap = fetchBalance(inited)
            if newCap != capacity:
                printCapacityDiff(capacity, newCap)
                balance = fetchBalance(inited, funds='total')
                printBalance(balance)
                log('評価額{}円'.format(calcMoney(balance, value)))
                capacity = newCap
            time.sleep(4)
            cooldown -= 1
        except Exception as e:
            log(traceback.format_exc())
            log(e)
            printBalance(capacity)
            time.sleep(10)
    return 0


def printBalance(capacity):
    """資産を表示."""
    if capacity is None:
        return
    b = capacity['bitbank']
    h = capacity['hitbtc2']
    s = '\n'.join([
        '資産',
        '  bitbank {}XRP {}JPY {}BTC'.format(b['XRP'], b['JPY'], b['BTC']),
        '  hitbtc {}XRP {}BTC'.format(h['XRP'], h['BTC']),
        '  計 {}XRP {}JPY {}BTC'.format(
            b['XRP'] + h['XRP'], b['JPY'], b['BTC'] + h['BTC'])])
    log(s)


def printCapacityDiff(old, new):
    """資産変化を表示."""
    # new - oldが0であるはずが, 全て足してから全て引くことでは誤差が生じた
    # 計算順序に気をつける
    def diff(exchange, coin):
        return new[exchange][coin] - old[exchange][coin]
    if old is None:
        return None
    dx = diff('bitbank', 'XRP') + diff('hitbtc2', 'XRP')
    dj = diff('bitbank', 'JPY')
    db = diff('bitbank', 'BTC') + diff('hitbtc2', 'BTC')
    log('資産変化 {}XRP {}JPY {}BTC'.format(dx, dj, db))


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
    return {'hitbtc2': hitbtc2, 'bitbank': bitbank,
            'bitbank2': bitbank2}


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
    thresholdS = 1.006
    thresholdB = 1.003
    (ratioS, valS, pbjS, pbxS, phxS) = calcSellingTwice(
        bitbankJpy['bids'],
        bitbankXrp['bids'],
        hitbtc2['asks'], thresholdS)
    (ratioB, valB, pbjB, pbxB, phxB) = calcBuyingTwice(
        bitbankJpy['asks'],
        bitbankXrp['asks'],
        hitbtc2['bids'], thresholdB)
    log((ratioS, valS, ratioB, valB))
    doTrade = (
        1 if ratioS >= thresholdS else  # 2回売る
        -1 if ratioB >= thresholdB else  # 2回買う
        0)
    if not doTrade:
        return False

    # 指値価格
    pbj = pbjS if doTrade == 1 else pbjB  # pbj BTC per JPY in bitbank
    pbb = 1 / pbj  # pbb JPY per BTC
    pbx = pbxS if doTrade == 1 else pbxB  # pbx JPY per XRP
    phx = phxS if doTrade == 1 else phxB  # phx BTC per XRP in hitbtc
    capS = min([
        capacity['bitbank']['XRP'],
        capacity['bitbank']['JPY'] / pbx,
        capacity['hitbtc2']['BTC'] / pbj / pbx])
    capB = min([
        capacity['bitbank']['JPY'] / pbx,
        capacity['bitbank']['BTC'] / pbj / pbx,
        capacity['hitbtc2']['XRP']])
    cap = capS if doTrade == 1 else capB
    val = min([cap * 0.79, valS if doTrade == 1 else valB])
    if val < 50:
        s = '\n'.join([
            '  元手不足',
            '    bitbank {}XRP {}JPY={}XRP {}BTC={}XRP'.format(
                capacity['bitbank']['XRP'], capacity['bitbank']['JPY'],
                capacity['bitbank']['JPY'] / pbx, capacity['bitbank']['BTC'],
                capacity['bitbank']['BTC'] / pbj / pbx),
            '    hitbtc {}XRP {}BTC={}XRP'.format(
                capacity['hitbtc2']['XRP'], capacity['hitbtc2']['BTC'],
                capacity['hitbtc2']['BTC'] / phx)])
        log(s)
        return False
    vbb = round(val * pbx * pbj, 4)
    vbx = round(vbb * pbb / pbx, 4)
    vhx = int(round(vbx, 0))

    log('\n'.join([
        '  tradeChance {}XRP'.format(val),
        '    {}JPYを1JPY{}BTCで{}'.format(
            vbb * pbb, pbj, '売' if doTrade == 1 else '買'),
        '      ={}BTCを1BTC{}JPYで{}'.format(
            vbb, pbb, '買' if doTrade == 1 else '売'),
        '    {}XRPを1XRP{}JPYで{}'.format(
            vbx, pbx, '売' if doTrade == 1 else '買'),
        '    {}XRPを1XRP{}BTCで{}'.format(
            vhx, phx, '買' if doTrade == 1 else '売'),
        '    {}XRP {}JPY {}BTC'.format(
            doTrade * (vhx - vbx),
            doTrade * (vbx * pbx - vbb * pbb),
            doTrade * (vbb - vhx * phx))]))

    # TODO 売買量をいじって偏りをなおす
    if doTrade == 1:  # 2回売る
        log('\n'.join([
            'sell bitbank XRP/JPY {}XRP {}JPY per XRP'.format(vbx, pbx),
            'buy bitbank BTC/JPY {}BTC {}JPY per BTC'.format(vbb, pbb),
            'buy hitbtc2 XRP/BTC {}XRP'.format(vhx)]))
        if production:
            el = asyncio.get_event_loop()
            bx = inited['bitbank'].create_order(
                'XRP/JPY', 'market', 'sell', vbx, pbx)
            bj = inited['bitbank2'].create_order(
                'BTC/JPY', 'market', 'buy', vbb, pbb)
            hx = inited['hitbtc2'].create_market_buy_order('XRP/BTC', vhx)
            res = el.run_until_complete(asyncio.gather(bx, bj, hx))
            log(res)
    elif doTrade == -1:  # 2回買う
        log('\n'.join([
            'buy bitbank XRP/JPY {}XRP {}JPY per XRP'.format(vbx, pbx),
            'sell bitbank BTC/JPY {}BTC {}JPY per BTC'.format(vbb, pbb),
            'sell hitbtc2 XRP/BTC {}XRP'.format(vhx)]))
        if production:
            el = asyncio.get_event_loop()
            bx = inited['bitbank'].create_order(
                'XRP/JPY', 'market', 'buy', vbx, 1)
            bj = inited['bitbank2'].create_order(
                'BTC/JPY', 'market', 'sell', vbb, pbb)
            hx = inited['hitbtc2'].create_market_sell_order('XRP/BTC', vhx)
            res = el.run_until_complete(asyncio.gather(bx, bj, hx))
            log(res)
    return True


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


def fetchBalance(inited, funds='free'):
    """資金取得."""
    el = asyncio.get_event_loop()
    cap = el.run_until_complete(asyncio.gather(
        inited['hitbtc2'].fetch_balance(),
        inited['bitbank'].fetch_balance()))
    newCap = {'hitbtc2': cap[0][funds], 'bitbank': cap[1][funds]}
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
