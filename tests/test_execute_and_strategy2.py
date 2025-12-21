import datetime
from orderbook import OrderBook
from strategy import execute_strategy, ARBITRAGE_SECURITIES
from execute_trade import _extract_currency


def test_extract_currency_variants():
    assert _extract_currency('AL30-0002-C-CT-USD') == 'USD'
    assert _extract_currency('AL30-0002-C-CT-ARS') == 'ARS'
    assert _extract_currency('AL30D-0002-C-CT-USD') == 'USD'
    assert _extract_currency('SOME-SEC-USD-EXTRA') == 'USD'
    assert _extract_currency('unknown-secu') == 'ARS'


def make_order_book_with_levels(security, best_offer_price, best_offer_qty, best_bid_price, best_bid_qty):
    ob = OrderBook(security)
    # Set simple one-level book
    ob.update_offers([best_offer_price], [best_offer_qty])
    ob.update_bids([best_bid_price], [best_bid_qty])
    return ob


def test_execute_strategy_no_negative_usd():
    # Build minimal order_books matching ARBITRAGE_SECURITIES
    order_books = {}
    # AL30 pair (buy side)
    al_peso = ARBITRAGE_SECURITIES['AL30']['peso_security']
    al_dollar = ARBITRAGE_SECURITIES['AL30']['dollar_security']
    order_books[al_peso] = make_order_book_with_levels(al_peso, best_offer_price=1000.0, best_offer_qty=1000, best_bid_price=995.0, best_bid_qty=1000)
    order_books[al_dollar] = make_order_book_with_levels(al_dollar, best_offer_price=51.0, best_offer_qty=1000, best_bid_price=50.0, best_bid_qty=1000)

    # GD30 pair (sell side)
    gd_peso = ARBITRAGE_SECURITIES['GD30']['peso_security']
    gd_dollar = ARBITRAGE_SECURITIES['GD30']['dollar_security']
    order_books[gd_peso] = make_order_book_with_levels(gd_peso, best_offer_price=1200.0, best_offer_qty=1000, best_bid_price=1195.0, best_bid_qty=1000)
    order_books[gd_dollar] = make_order_book_with_levels(gd_dollar, best_offer_price=56.0, best_offer_qty=1000, best_bid_price=55.0, best_bid_qty=1000)

    # Initial balances: plenty of ARS, small USD (0)
    ars_balance = {'balance': 100_000_000.0}
    usd_balance = {'balance': 0.0}

    # Execute one strategy run
    executed = execute_strategy(order_books, datetime.datetime.now(), ars_balance, usd_balance, stats={})

    # After execution, USD should not be negative
    assert usd_balance['balance'] >= 0.0
    # ARS balance should be finite number
    assert isinstance(ars_balance['balance'], float)
