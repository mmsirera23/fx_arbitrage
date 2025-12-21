"""
Trading strategy module for triangular arbitrage using AL30 and GD30 bonds.
"""

from typing import Dict, Optional, Tuple
from orderbook import OrderBook
from execute_trade import execute_trade
import time
import logging

# Module logger
logger = logging.getLogger('fx_arbitrage')

# Keep track of the last skipped opportunity to avoid repeated logging
_last_skipped_opportunity = None


def _opportunity_signature(arbitrage_info: Dict) -> Tuple[str, str, float]:
    """Create a lightweight signature for an opportunity to detect repeats."""
    return (
        arbitrage_info.get('buy_pair_name'),
        arbitrage_info.get('sell_pair_name'),
        round(arbitrage_info.get('arbitrage_profit_pct', 0.0), 6)
    )


def _should_log_skipped(arbitrage_info: Dict) -> bool:
    """Return True if this skipped opportunity has not been logged recently.

    Updates the module-level `_last_skipped_opportunity` when a new one is seen.
    """
    global _last_skipped_opportunity
    sig = _opportunity_signature(arbitrage_info)
    if _last_skipped_opportunity == sig:
        return False
    _last_skipped_opportunity = sig
    return True


def _reset_last_skipped() -> None:
    """Reset the last skipped opportunity marker."""
    global _last_skipped_opportunity
    _last_skipped_opportunity = None
# Hardcoded security pairs available for FX arbitrage
# These are the 4 instruments: AL30 (pesos), AL30D (dollars), GD30 (pesos), GD30D (dollars)
# Add more pairs as needed
ARBITRAGE_SECURITIES = {
    'AL30': {
        'peso_security': 'AL30-0002-C-CT-ARS',    # AL30 in pesos
        'dollar_security': 'AL30D-0002-C-CT-USD'   # AL30D in dollars
    },
    'GD30': {
        'peso_security': 'GD30-0002-C-CT-ARS',    # GD30 in pesos
        'dollar_security': 'GD30D-0002-C-CT-USD'  # GD30D in dollars
    }
}
# Market fees (comisiones de mercado)
# According to "DERECHOS DE MERCADO SOBRE OPERACIONES" table:
# "Públicos - Obligaciones Negociables": 0.0100% (0.0001 in decimal)
MARKET_FEE_RATE = 0.0001  # 0.0100% = 0.0001


def _find_security_by_prefix(order_books: Dict[str, OrderBook], prefix: str) -> Optional[str]:
    """
    Find a security in order books by prefix.
    
    Args:
        order_books: Dictionary of order books
        prefix: Prefix to search for
        
    Returns:
        Security key if found, None otherwise
    """
    for security in order_books.keys():
        if security.startswith(prefix):
            return security
    return None


def calculate_implicit_fx_rate(pesos_price: float, dolares_price: float) -> float:
    """
    Calculate implicit FX rate from bond prices.
    
    Args:
        pesos_price: Price of the peso-denominated bond
        dolares_price: Price of the dollar-denominated bond
        
    Returns:
        Implicit FX rate (pesos per dollar)
    """
    if dolares_price == 0:
        return 0.0
    return pesos_price / dolares_price


def _evaluate_arbitrage_direction(
    order_books: Dict[str, OrderBook],
    buy_pair: Tuple[str, str],  # (peso_security, dollar_security)
    sell_pair: Tuple[str, str]  # (peso_security, dollar_security)
) -> Optional[Dict]:
    """
    Evaluate an arbitrage opportunity in one direction.
    
    Direction: Buy dollars via buy_pair, sell dollars via sell_pair
    
    Args:
        order_books: Dictionary of order books
        buy_pair: (peso_security, dollar_security) pair to buy dollars
        sell_pair: (peso_security, dollar_security) pair to sell dollars
        
    Returns:
        Dictionary with arbitrage details if opportunity exists, None otherwise
    """
    peso_buy_sec, dollar_buy_sec = buy_pair
    peso_sell_sec, dollar_sell_sec = sell_pair
    
    # Get order books
    peso_buy_book = order_books[peso_buy_sec]
    dollar_buy_book = order_books[dollar_buy_sec]
    peso_sell_book = order_books[peso_sell_sec]
    dollar_sell_book = order_books[dollar_sell_sec]
    
    # Get best prices
    peso_buy_offer = peso_buy_book.get_best_offer()  # Price to buy peso bond
    dollar_buy_bid = dollar_buy_book.get_best_bid()  # Price to sell dollar bond
    peso_sell_bid = peso_sell_book.get_best_bid()    # Price to sell peso bond
    dollar_sell_offer = dollar_sell_book.get_best_offer()  # Price to buy dollar bond
    
    if (peso_buy_offer is None or dollar_buy_bid is None or 
        peso_sell_bid is None or dollar_sell_offer is None):
        return None
    
    # Store original prices (for order book updates)
    peso_buy_price_original = peso_buy_offer[0]
    dollar_buy_price_original = dollar_buy_bid[0]
    peso_sell_price_original = peso_sell_bid[0]
    dollar_sell_price_original = dollar_sell_offer[0]
    
    # Adjust prices with transaction fees for profit calculation
    # When buying: price * (1 + fee) - we pay more
    # When selling: price * (1 - fee) - we receive less
    peso_buy_price_with_fee = peso_buy_price_original * (1 + MARKET_FEE_RATE)
    dollar_buy_price_with_fee = dollar_buy_price_original * (1 - MARKET_FEE_RATE)  # Selling, so we receive less
    peso_sell_price_with_fee = peso_sell_price_original * (1 - MARKET_FEE_RATE)  # Selling, so we receive less
    dollar_sell_price_with_fee = dollar_sell_price_original * (1 + MARKET_FEE_RATE)  # Buying, so we pay more
    
    # Calculate implicit FX rates with fees included
    # Buy dollars: buy peso_buy, sell dollar_buy
    fx_buy = calculate_implicit_fx_rate(peso_buy_price_with_fee, dollar_buy_price_with_fee)
    
    # Sell dollars: buy dollar_sell, sell peso_sell
    fx_sell = calculate_implicit_fx_rate(peso_sell_price_with_fee, dollar_sell_price_with_fee)
    
    # Check for arbitrage opportunity
    if fx_buy < fx_sell and fx_buy > 0 and fx_sell > 0:
        profit_pct = ((fx_sell - fx_buy) / fx_buy) * 100
        
        return {
            'buy_pair': buy_pair,
            'sell_pair': sell_pair,
            'peso_buy_security': peso_buy_sec,
            'dollar_buy_security': dollar_buy_sec,
            'peso_sell_security': peso_sell_sec,
            'dollar_sell_security': dollar_sell_sec,
            # Prices with fees (for profit calculations)
            'peso_buy_price': peso_buy_price_with_fee,
            'peso_buy_volume': peso_buy_offer[1],
            'dollar_buy_price': dollar_buy_price_with_fee,
            'dollar_buy_volume': dollar_buy_bid[1],
            'peso_sell_price': peso_sell_price_with_fee,
            'peso_sell_volume': peso_sell_bid[1],
            'dollar_sell_price': dollar_sell_price_with_fee,
            'dollar_sell_volume': dollar_sell_offer[1],
            # Original prices (for order book updates)
            'peso_buy_price_original': peso_buy_price_original,
            'dollar_buy_price_original': dollar_buy_price_original,
            'peso_sell_price_original': peso_sell_price_original,
            'dollar_sell_price_original': dollar_sell_price_original,
            'implicit_fx_buy': fx_buy,
            'implicit_fx_sell': fx_sell,
            'arbitrage_profit_pct': profit_pct
        }
    
    return None


def check_arbitrage_opportunity(order_books: Dict[str, OrderBook]) -> Optional[Dict]:
    """
    Check for arbitrage opportunities using the hardcoded security pairs.
    Evaluates all possible combinations between AL30 and GD30 pairs.
    
    Args:
        order_books: Dictionary of order books by security
        
    Returns:
        Dictionary with the best arbitrage opportunity, None if none found
    """
    # Build bond pairs from hardcoded securities
    # Try to find actual securities in order books by prefix matching
    bond_pairs = {}
    
    for pair_name, securities in ARBITRAGE_SECURITIES.items():
        peso_sec = _find_security_by_prefix(order_books, securities['peso_security'].split('-')[0] + '-')
        dollar_sec = _find_security_by_prefix(order_books, securities['dollar_security'].split('-')[0] + '-')
        
        if peso_sec and dollar_sec:
            bond_pairs[pair_name] = (peso_sec, dollar_sec)
    
    
    # Generate all combinations of pairs (buy from one, sell via another)
    best_opportunity = None
    best_profit = -1.0
    
    # Evaluate all possible directions
    for buy_pair_name, buy_pair in bond_pairs.items():
        for sell_pair_name, sell_pair in bond_pairs.items():
            if buy_pair_name == sell_pair_name:
                continue  # Skip same pair
            
            # Evaluate this direction
            opportunity = _evaluate_arbitrage_direction(order_books, buy_pair, sell_pair)
            
            if opportunity and opportunity['arbitrage_profit_pct'] > best_profit:
                best_profit = opportunity['arbitrage_profit_pct']
                best_opportunity = opportunity
                best_opportunity['buy_pair_name'] = buy_pair_name
                best_opportunity['sell_pair_name'] = sell_pair_name
    
    return best_opportunity


def execute_arbitrage_opportunities_iteratively(
    order_books: Dict[str, OrderBook],
    timestamp,
    ars_balance: Dict[str, float],
    usd_balance: Dict[str, float],
    max_iterations: int = 100,
    stats: Optional[Dict] = None
) -> int:
    """
    Execute arbitrage opportunities iteratively until no more opportunities exist.
    This function checks for opportunities, executes them, and re-checks until
    no more opportunities are found or max_iterations is reached.
    
    Args:
        order_books: Dictionary of order books by security
        timestamp: Current timestamp
        ars_balance: Dictionary with ARS balance (will be updated)
        usd_balance: Dictionary with USD balance (will be updated)
        max_iterations: Maximum number of iterations to prevent infinite loops
        
    Returns:
        Number of arbitrage opportunities executed
    """
    executed_count = 0
    iteration = 0
    
    while iteration < max_iterations:
        # Check if there's an arbitrage opportunity
        opportunity_executed = execute_strategy(order_books, timestamp, ars_balance, usd_balance, stats=stats)
        
        if not opportunity_executed:
            # No more opportunities, break the loop
            break
        
        executed_count += 1
        iteration += 1
        
        # After executing, the order books have been updated by execute_trade()
        # Continue the loop to check for new opportunities with updated order books
    
    if iteration >= max_iterations:
        print(f"[WARNING] Reached maximum iterations ({max_iterations}) in arbitrage opportunity search")
    
    return executed_count


def calculate_max_volume(arbitrage_info: Dict) -> Tuple[float, int]:
    """
    Calculate the maximum FX volume (in dollars) and nominals that can be traded in the arbitrage.
    
    Args:
        arbitrage_info: Dictionary with arbitrage opportunity details
        
    Returns:
        Tuple (max_fx_volume, max_nominals) where:
            - max_fx_volume: Maximum FX volume in dollars that can be traded
            - max_nominals: Maximum integer nominals that can be traded
        Returns (0, 0) if no volume is available
    """
    # Buy leg: min(peso_buy_volume, dollar_buy_volume)
    max_nominals_buy = min(
        arbitrage_info['peso_buy_volume'],
        arbitrage_info['dollar_buy_volume']
    )
    
    # Sell leg: min(dollar_sell_volume, peso_sell_volume)
    max_nominals_sell = min(
        arbitrage_info['dollar_sell_volume'],
        arbitrage_info['peso_sell_volume']
    )
    
    # Maximum integer nominals (must be at least 1)
    # int() on positive floats does floor rounding (truncates towards zero)
    # For example: int(5.9) = 5, int(5.1) = 5
    max_nominals = int(min(max_nominals_buy, max_nominals_sell))
    
    if max_nominals <= 0:
        return (0.0, 0)
    
    # Calculate FX volume with integer nominals
    # We need to ensure we can buy and sell the same amount of dollars
    dollars_buy = max_nominals * arbitrage_info['dollar_buy_price']
    dollars_sell = max_nominals * arbitrage_info['dollar_sell_price']
    
    # Return the minimum FX volume (what we can actually trade)
    max_fx_volume = min(dollars_buy, dollars_sell)
    
    return (max_fx_volume, max_nominals)


def execute_arbitrage_trade(
    order_books: Dict[str, OrderBook],
    nominals: int,
    arbitrage_info: Dict
) -> Dict:
    """
    Execute the arbitrage trade by updating order books.
    
    Args:
        order_books: Dictionary of order books by security
        nominals: Integer number of nominals to trade
        arbitrage_info: Dictionary with arbitrage opportunity details
        
    Returns:
        Dictionary with trade execution details and returns
    """
    if nominals <= 0:
        raise ValueError("Cannot execute trade with zero or negative nominals")
    
    # Leg 1: Buy peso bond (buy pair)
    peso_buy_quantity = nominals
    peso_buy_cost = peso_buy_quantity * arbitrage_info['peso_buy_price']
    
    # Leg 2: Sell dollar bond (buy pair) - receive dollars
    dollar_buy_quantity = nominals
    dollar_buy_proceeds = dollar_buy_quantity * arbitrage_info['dollar_buy_price']
    
    # Leg 3: Buy dollar bond (sell pair) - spend dollars
    dollar_sell_quantity = nominals
    dollar_sell_cost = dollar_sell_quantity * arbitrage_info['dollar_sell_price']
    
    # Leg 4: Sell peso bond (sell pair) - receive pesos
    peso_sell_quantity = nominals
    peso_sell_proceeds = peso_sell_quantity * arbitrage_info['peso_sell_price']
    
    # Note: Order books will be updated by execute_trade() after each trade execution
    
    # Net result: we start with pesos, end with pesos
    net_profit_pesos = peso_sell_proceeds - peso_buy_cost
    
    # Calculate actual FX volume traded (in dollars)
    fx_volume = nominals * min(arbitrage_info['dollar_buy_price'], arbitrage_info['dollar_sell_price'])
    
    return {
        'volume': fx_volume,
        'nominals': nominals,
        'peso_buy_cost': peso_buy_cost,
        'dollar_buy_proceeds': dollar_buy_proceeds,
        'dollar_sell_cost': dollar_sell_cost,
        'peso_sell_proceeds': peso_sell_proceeds,
        'net_profit_pesos': net_profit_pesos,
        'return_pct': (net_profit_pesos / peso_buy_cost) * 100 if peso_buy_cost > 0 else 0
    }



def execute_strategy(
    order_books: Dict[str, OrderBook], 
    timestamp,
    ars_balance: Dict[str, float],
    usd_balance: Dict[str, float]
    , stats: Optional[Dict] = None
) -> bool:
    """
    Execute a single arbitrage opportunity if one exists.
    
    Args:
        order_books: Dictionary of order books by security
        timestamp: Current timestamp
        ars_balance: Dictionary with ARS balance (will be updated)
        usd_balance: Dictionary with USD balance (will be updated)
        
    Returns:
        True if an arbitrage opportunity was executed, False otherwise
    """
    # Check for arbitrage opportunity
    arbitrage_info = check_arbitrage_opportunity(order_books)
    
    if arbitrage_info is None:
        # No opportunity found -> reset last skipped marker
        _reset_last_skipped()
        return False
    
    # Calculate maximum volume and nominals based on order book
    max_fx_volume, max_nominals = calculate_max_volume(arbitrage_info)
    
    if max_nominals <= 0 or max_fx_volume <= 0:
        # No sufficient volume available for this arbitrage opportunity
        if _should_log_skipped(arbitrage_info):
            logger.info("[ARBITRAGE] Opportunity detected but insufficient volume available")
            logger.info("  Buy Pair: %s, Sell Pair: %s", arbitrage_info['buy_pair_name'], arbitrage_info['sell_pair_name'])
            logger.info("  Potential Profit (after fees): %.4f%%", arbitrage_info['arbitrage_profit_pct'])
            logger.debug("  Available volumes:")
            logger.debug("    Buy leg: %.2f nominals", min(arbitrage_info['peso_buy_volume'], arbitrage_info['dollar_buy_volume']))
            logger.debug("    Sell leg: %.2f nominals", min(arbitrage_info['dollar_sell_volume'], arbitrage_info['peso_sell_volume']))
            logger.info("  Maximum tradable nominals: %d (minimum required: 1)", max_nominals)
            logger.info("  Skipping trade execution")
        return False
    
    # Store initial balances
    initial_ars = ars_balance['balance']
    initial_usd = usd_balance['balance']
    
    MARKET_FEE_RATE = 0.0001

    # Determine limits from order books
    max_nominals_sell = min(
        arbitrage_info['dollar_sell_volume'],
        arbitrage_info['peso_sell_volume']
    )

    # Buy side limits (orderbook + ARS balance)
    max_nominals_buy_orderbook = min(
        arbitrage_info['peso_buy_volume'],
        arbitrage_info['dollar_buy_volume']
    )

    peso_buy_price_original = arbitrage_info['peso_buy_price_original']
    peso_buy_cost_per_nominal = peso_buy_price_original * (1 + MARKET_FEE_RATE)

    # Compute how many nominals ARS can afford (float) and limit by orderbook
    if initial_ars < peso_buy_cost_per_nominal:
        max_nominals_buy = 0.0
    else:
        max_nominals_buy = min(max_nominals_buy_orderbook, initial_ars / peso_buy_cost_per_nominal)

    # USD proceeds per nominal from selling dollar bond in buy-pair (step 2)
    dollar_buy_price_original = arbitrage_info['dollar_buy_price_original']
    dollar_buy_proceeds_per_nominal = dollar_buy_price_original * (1 - MARKET_FEE_RATE)

    # USD cost per nominal to buy dollar bond in sell-pair (step 3)
    dollar_sell_price_original = arbitrage_info['dollar_sell_price_original']
    dollar_sell_cost_per_nominal = dollar_sell_price_original * (1 + MARKET_FEE_RATE)

    # USD available after performing the buy-pair sell (step 2)
    usd_available_after_step2 = initial_usd + (max_nominals_buy * dollar_buy_proceeds_per_nominal)

    # Max nominals limited by USD availability for step 3
    if dollar_sell_cost_per_nominal > 0:
        max_nominals_by_usd = usd_available_after_step2 / dollar_sell_cost_per_nominal
    else:
        max_nominals_by_usd = 0.0

    # Ensure final USD after all four trades will not be negative.
    # USD net change per nominal = proceeds from selling in buy-pair - cost to buy in sell-pair
    usd_delta_per_nominal = dollar_buy_proceeds_per_nominal - dollar_sell_cost_per_nominal
    # Do not preemptively cap final nominals based on USD (allow execution and warn after)
    max_nominals_by_final_usd = float('inf')

    # Final nominal capacity (float). Avoid truncating to int until final decision.
    final_nominals_capacity = min(max_nominals_buy, max_nominals_sell, max_nominals_by_usd, max_nominals_by_final_usd)

    actual_nominals = int(final_nominals_capacity)

    if actual_nominals <= 0:
        if _should_log_skipped(arbitrage_info):
            logger.info("[ARBITRAGE] Opportunity detected but insufficient volume or balance")
            logger.info("  Buy Pair: %s, Sell Pair: %s", arbitrage_info['buy_pair_name'], arbitrage_info['sell_pair_name'])
            logger.info("  Potential Profit (after fees): %.4f%%", arbitrage_info['arbitrage_profit_pct'])
            logger.debug("  Max nominals (buy/orderbook): %.2f", max_nominals_buy)
            logger.debug("  Max nominals (sell/orderbook): %.2f", max_nominals_sell)
            logger.debug("  Max nominals (by USD availability): %.2f", max_nominals_by_usd)
            logger.debug("  Available ARS balance: %,.2f", initial_ars)
            logger.debug("  Available USD balance: %,.2f", initial_usd)
            logger.info("  Skipping trade execution")
        return False

    trade_result = execute_arbitrage_trade(order_books, actual_nominals, arbitrage_info)

    # Print trade details
    logger.info("%s", "="*60)
    logger.info("ARBITRAGE OPPORTUNITY DETECTED at %s", timestamp)
    logger.info("%s", "="*60)
    logger.info("Buy Pair: %s", arbitrage_info['buy_pair_name'])
    logger.info("Sell Pair: %s", arbitrage_info['sell_pair_name'])
    
    # Detailed FX calculation breakdown
    logger.info("%s", "─"*60)
    logger.info("IMPLICIT FX CALCULATION DETAILS:")
    logger.info("%s", "─"*60)
    
    # FX Buy calculation
    logger.info("FX Buy (after fees): %.4f ARS/USD", arbitrage_info['implicit_fx_buy'])
    logger.debug("  To buy USD via %s:", arbitrage_info['buy_pair_name'])
    logger.debug("    Buy %s:", arbitrage_info['peso_buy_security'])
    logger.debug("      Price (original): %.2f ARS", arbitrage_info['peso_buy_price_original'])
    logger.debug("      Price (with fees): %.2f ARS", arbitrage_info['peso_buy_price'])
    logger.debug("      Available volume: %.2f nominals", arbitrage_info['peso_buy_volume'])
    logger.debug("    Sell %s:", arbitrage_info['dollar_buy_security'])
    logger.debug("      Price (original): %.2f USD", arbitrage_info['dollar_buy_price_original'])
    logger.debug("      Price (with fees): %.2f USD", arbitrage_info['dollar_buy_price'])
    logger.debug("      Available volume: %.2f nominals", arbitrage_info['dollar_buy_volume'])
    logger.debug("    Calculation: %.2f / %.2f = %.4f", arbitrage_info['peso_buy_price'], arbitrage_info['dollar_buy_price'], arbitrage_info['implicit_fx_buy'])
    
    # FX Sell calculation
    logger.info("FX Sell (after fees): %.4f ARS/USD", arbitrage_info['implicit_fx_sell'])
    logger.debug("  To sell USD via %s:", arbitrage_info['sell_pair_name'])
    logger.debug("    Buy %s:", arbitrage_info['dollar_sell_security'])
    logger.debug("      Price (original): %.2f USD", arbitrage_info['dollar_sell_price_original'])
    logger.debug("      Price (with fees): %.2f USD", arbitrage_info['dollar_sell_price'])
    logger.debug("      Available volume: %.2f nominals", arbitrage_info['dollar_sell_volume'])
    logger.debug("    Sell %s:", arbitrage_info['peso_sell_security'])
    logger.debug("      Price (original): %.2f ARS", arbitrage_info['peso_sell_price_original'])
    logger.debug("      Price (with fees): %.2f ARS", arbitrage_info['peso_sell_price'])
    logger.debug("      Available volume: %.2f nominals", arbitrage_info['peso_sell_volume'])
    logger.debug("    Calculation: %.2f / %.2f = %.4f", arbitrage_info['peso_sell_price'], arbitrage_info['dollar_sell_price'], arbitrage_info['implicit_fx_sell'])
    
    logger.info("Arbitrage Profit (after fees): %.4f%%", arbitrage_info['arbitrage_profit_pct'])
    logger.info("Trade Execution:")
    logger.info("  FX Volume (dollars): %.2f", trade_result['volume'])
    logger.info("  Nominals: %d", trade_result['nominals'])
    logger.info("  Peso Buy Cost (pesos, with fees): %.2f", trade_result['peso_buy_cost'])
    logger.info("  Dollar Buy Proceeds (dollars, with fees): %.2f", trade_result['dollar_buy_proceeds'])
    logger.info("  Dollar Sell Cost (dollars, with fees): %.2f", trade_result['dollar_sell_cost'])
    logger.info("  Peso Sell Proceeds (pesos, with fees): %.2f", trade_result['peso_sell_proceeds'])
    logger.info("  Net Profit (pesos, after fees): %.2f", trade_result['net_profit_pesos'])
    logger.info("  Return (after fees): %.4f%%", trade_result['return_pct'])
    logger.info("Balance Changes:")
    logger.info("  ARS: %,.2f -> %,.2f (change: %+.2f)", initial_ars, ars_balance['balance'], ars_balance['balance'] - initial_ars)
    logger.info("  USD: %,.2f -> %,.2f (change: %+.2f)", initial_usd, usd_balance['balance'], usd_balance['balance'] - initial_usd)
    logger.debug("Balance snapshot BEFORE execution:")
    logger.debug("  ARS: %,.2f", initial_ars)
    logger.debug("  USD: %,.2f", initial_usd)

    # Execute 4 trades by sending orders to market via FIX
    nominals = trade_result['nominals']

    start = time.perf_counter()

    # Trade 1: Buy peso bond (buy pair) - buy from offers (is_bid=False)
    order_metrics = []
    res = execute_trade(
        arbitrage_info['peso_buy_security'],
        arbitrage_info['peso_buy_price_original'],
        nominals,
        timestamp,
        order_book=order_books[arbitrage_info['peso_buy_security']],
        is_bid=False,
        ars_balance=ars_balance,
        usd_balance=usd_balance
    )
    if res:
        order_metrics.append(res)

    # Trade 2: Sell dollar bond (buy pair) - sell to bids (is_bid=True)
    res = execute_trade(
        arbitrage_info['dollar_buy_security'],
        arbitrage_info['dollar_buy_price_original'],
        nominals,
        timestamp,
        order_book=order_books[arbitrage_info['dollar_buy_security']],
        is_bid=True,
        ars_balance=ars_balance,
        usd_balance=usd_balance
    )
    if res:
        order_metrics.append(res)

    # Trade 3: Buy dollar bond (sell pair) - buy from offers (is_bid=False)
    res = execute_trade(
        arbitrage_info['dollar_sell_security'],
        arbitrage_info['dollar_sell_price_original'],
        nominals,
        timestamp,
        order_book=order_books[arbitrage_info['dollar_sell_security']],
        is_bid=False,
        ars_balance=ars_balance,
        usd_balance=usd_balance
    )
    if res:
        order_metrics.append(res)

    # Trade 4: Sell peso bond (sell pair) - sell to bids (is_bid=True)
    res = execute_trade(
        arbitrage_info['peso_sell_security'],
        arbitrage_info['peso_sell_price_original'],
        nominals,
        timestamp,
        order_book=order_books[arbitrage_info['peso_sell_security']],
        is_bid=True,
        ars_balance=ars_balance,
        usd_balance=usd_balance
    )
    if res:
        order_metrics.append(res)

    end = time.perf_counter()
    latency_ms = (end - start) * 1000.0

    # PnL after execution (balances updated in execute_trade)
    final_ars = ars_balance['balance']
    final_usd = usd_balance['balance']
    pnl_ars = final_ars - initial_ars
    pnl_usd = final_usd - initial_usd

    # Update stats accumulator if provided
    if stats is not None:
        stats.setdefault('total_latency_ms', 0.0)
        stats.setdefault('total_order_latency_ms', 0.0)
        stats.setdefault('total_pnl_ars', 0.0)
        stats.setdefault('total_pnl_usd', 0.0)
        stats.setdefault('trades_executed', 0)
        stats.setdefault('orders_executed', 0)

        stats['total_latency_ms'] += latency_ms
        # sum per-order latencies
        sum_order_latency = sum((m.get('latency_ms', 0.0) for m in order_metrics))
        stats['total_order_latency_ms'] += sum_order_latency
        stats['total_pnl_ars'] += pnl_ars
        stats['total_pnl_usd'] += pnl_usd
        stats['trades_executed'] += 1
        stats['orders_executed'] += len(order_metrics)

    logger.info("Execution latency: %.2f ms", latency_ms)
    logger.info("Balance Changes AFTER execution:")
    logger.info("  ARS: %,.2f -> %,.2f (change: %+.2f)", initial_ars, final_ars, pnl_ars)
    logger.info("  USD: %,.2f -> %,.2f (change: %+.2f)", initial_usd, final_usd, pnl_usd)
    if final_usd < 0:
        logger.warning("  WARNING: USD balance is negative after execution: %.2f", final_usd)

    logger.info("%s", "="*60)

    # Successful execution -> reset last skipped marker so future identical
    # opportunities will be logged again if they reappear
    _reset_last_skipped()

    return True
