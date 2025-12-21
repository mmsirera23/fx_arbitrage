"""
Module for executing trades in the market.
This module handles the actual trade execution and order submission to the market via FIX protocol.

TODO: Implement FIX protocol integration to send orders to the market.
"""

from typing import Dict, Optional
from datetime import datetime
from orderbook import OrderBook
import time


def _extract_currency(security: str) -> str:
    """
    Extract currency from security identifier.
    
    Args:
        security: Security identifier
        
    Returns:
        Currency code (ARS or USD)
    """
    sec = security.upper()
    # Common explicit mentions
    if 'USD' in sec:
        return 'USD'
    if 'ARS' in sec:
        return 'ARS'
    # Fallback heuristics: tokens separated by '-' may include currency codes
    tokens = [t for t in sec.replace('_', '-').split('-') if t]
    for t in tokens:
        if t in ('USD', 'US', 'D', 'DUSD'):
            return 'USD'
        if t in ('ARS', 'AR', 'P', 'PESOS'):
            return 'ARS'
    # Default to ARS to be conservative
    return 'ARS'


def execute_trade(
    security: str, 
    price: float, 
    volume: float, 
    timestamp,
    order_book: Optional[OrderBook] = None,
    is_bid: Optional[bool] = None,
    ars_balance: Optional[Dict[str, float]] = None,
    usd_balance: Optional[Dict[str, float]] = None
) -> Optional[Dict]:
    """
    Execute a single trade by sending an order to the market via FIX protocol.
    Updates the order book and balances after trade execution.
    
    Output format: timestamp, asset, currency, price, volume, price x volume
    
    Args:
        security: Security identifier (e.g., 'AL30-0002-C-CT-ARS')
        price: Execution price (original market price, without fees)
        volume: Volume (nominals) to trade
        timestamp: Timestamp of the trade execution
        order_book: Optional OrderBook to update after trade execution
        is_bid: Optional flag indicating if trade was on bid side (True) or offer side (False)
        ars_balance: Optional dictionary with ARS balance (will be updated)
        usd_balance: Optional dictionary with USD balance (will be updated)
        
    TODO: Implement FIX protocol integration to send order to the market.
    """
    # Format timestamp
    if hasattr(timestamp, 'strftime'):
        timestamp_str = timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')
    else:
        timestamp_str = str(timestamp)
    
    # Extract currency
    currency = _extract_currency(security)
    
    # Calculate price x volume (transaction value)
    pxq = price * volume
    
    # Calculate fees (0.0100% = 0.0001)
    MARKET_FEE_RATE = 0.0001
    fees = pxq * MARKET_FEE_RATE

    balance_before = None
    balance_after = None
    # Update balances based on trade side and currency
    # The logic is the same for both currencies:
    # - Selling (is_bid=True): receive (price * volume - fees)
    # - Buying (is_bid=False): spend (price * volume + fees)
    if ars_balance is not None and usd_balance is not None:
        # Determine which balance to update based on currency
        balance_to_update = ars_balance if currency == 'ARS' else usd_balance
        balance_before = float(balance_to_update.get('balance', 0.0))
        
        if is_bid:
            # Selling: receive (price * volume - fees)
            balance_to_update['balance'] += pxq - fees
        else:
            # Buying: spend (price * volume + fees)
            balance_to_update['balance'] -= pxq + fees
        balance_after = float(balance_to_update.get('balance', 0.0))

    # Print trade execution
    print(f"{timestamp_str}, {security}, {currency}, {price:.2f}, {volume:.2f}, {pxq:.2f}")

    # Send FIX order to market and measure latency (placeholder)
    start = time.perf_counter()
    try:
        send_fix_order(symbol=security, quantity=volume, price=price)
    except Exception as e:
        print(f"Error sending FIX order: {e}")
    # Update order book after trade execution
    if order_book is not None and is_bid is not None:
        _update_order_book_after_trade(order_book, price, volume, is_bid)
    end = time.perf_counter()

    latency_ms = (end - start) * 1000.0

    result = {
        'timestamp': timestamp_str,
        'symbol': security,
        'currency': currency,
        'price': price,
        'volume': volume,
        'pxq': pxq,
        'fees': fees,
        'latency_ms': latency_ms,
        'balance_change': None
    }

    if balance_before is not None and balance_after is not None:
        result['balance_change'] = balance_after - balance_before

    return result


def _update_order_book_after_trade(
    order_book: OrderBook,
    price: float,
    volume: float,
    is_bid: bool
) -> None:
    """
    Update order book after executing a trade by reducing volume at the specified price.
    This function is needed because we wan't receive the updated order book 
    after each trade from the exchange server side.
    
    Args:
        order_book: OrderBook to update
        price: Price level where trade was executed
        volume: Volume traded
        is_bid: True if trade was on bid side, False if on offer side
    """
    if is_bid:
        if price in order_book.bids:
            current_volume = order_book.bids[price]
            new_volume = current_volume - volume
            if new_volume <= 0:
                # Remove the price level if volume is exhausted
                del order_book.bids[price]
            else:
                order_book.bids[price] = new_volume
    else:
        if price in order_book.offers:
            current_volume = order_book.offers[price]
            new_volume = current_volume - volume
            if new_volume <= 0:
                # Remove the price level if volume is exhausted
                del order_book.offers[price]
            else:
                order_book.offers[price] = new_volume


def send_fix_order(symbol: str, quantity: float, price: float) -> None:
    """
    Send a FIX order to the market.
    This function is a placeholder for the actual FIX protocol implementation
    and we will suppose that the order was fulfilled as we are the fastest in 
    the market.
    
    Args:
        symbol: Security identifier
        quantity: Volume (nominals) to trade
        price: Execution price
    """
    print(f"Sending FIX order: {symbol}, {quantity}, {price}, {price * quantity}")
    print(f"Order fulfilled")