"""
Trading strategy module for triangular arbitrage using AL30 and GD30 bonds.
"""

from typing import Dict, Optional, Tuple
from orderbook import OrderBook
from execute_trade import execute_trade


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
    max_iterations: int = 100
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
        opportunity_executed = execute_strategy(order_books, timestamp, ars_balance, usd_balance)
        
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
        return False
    
    # Calculate maximum volume and nominals based on order book
    max_fx_volume, max_nominals = calculate_max_volume(arbitrage_info)
    
    if max_nominals <= 0 or max_fx_volume <= 0:
        # No sufficient volume available for this arbitrage opportunity
        print(f"[ARBITRAGE] Opportunity detected but insufficient volume available")
        print(f"  Buy Pair: {arbitrage_info['buy_pair_name']}, Sell Pair: {arbitrage_info['sell_pair_name']}")
        print(f"  Potential Profit (after fees): {arbitrage_info['arbitrage_profit_pct']:.4f}%")
        print(f"  Available volumes:")
        print(f"    Buy leg: {min(arbitrage_info['peso_buy_volume'], arbitrage_info['dollar_buy_volume']):.2f} nominals")
        print(f"    Sell leg: {min(arbitrage_info['dollar_sell_volume'], arbitrage_info['peso_sell_volume']):.2f} nominals")
        print(f"  Maximum tradable nominals: {max_nominals} (minimum required: 1)")
        print(f"  Skipping trade execution")
        return False
    
    # Store initial balances
    initial_ars = ars_balance['balance']
    initial_usd = usd_balance['balance']
    
    MARKET_FEE_RATE = 0.0001
    
    # Calculate maximum USD we can SELL (steps 3 and 4)
    # Step 3: Buy dollar bond (sell pair) - min volume between dollar_sell_volume and peso_sell_volume
    # Step 4: Sell peso bond (sell pair) - same nominals
    # The limiting factor is the minimum volume between these two orders
    max_nominals_sell = min(
        arbitrage_info['dollar_sell_volume'],
        arbitrage_info['peso_sell_volume']
    )
    dollar_sell_price_original = arbitrage_info['dollar_sell_price_original']
    # USD we can sell = volume of dollar bond we can buy (step 3)
    max_usd_sell = max_nominals_sell * dollar_sell_price_original
    
    # Calculate maximum USD we can PURCHASE (steps 1 and 2)
    # Step 1: Buy peso bond (buy pair) - limited by peso_buy_volume and ARS balance
    # Step 2: Sell dollar bond (buy pair) - limited by dollar_buy_volume
    # The limiting factor is the minimum between:
    #   - Order book volumes (peso_buy_volume, dollar_buy_volume)
    #   - ARS balance available (how much we can spend)
    
    # First, calculate max nominals from order book volumes
    max_nominals_buy_orderbook = min(
        arbitrage_info['peso_buy_volume'],
        arbitrage_info['dollar_buy_volume']
    )
    
    # Calculate max nominals we can afford with ARS balance
    peso_buy_price_original = arbitrage_info['peso_buy_price_original']
    peso_buy_cost_per_nominal = peso_buy_price_original * (1 + MARKET_FEE_RATE)
    
    if initial_ars < peso_buy_cost_per_nominal:
        # Not enough ARS even for 1 nominal
        max_nominals_buy_by_ars = 0
    else:
        max_nominals_buy_by_ars = int(initial_ars / peso_buy_cost_per_nominal)
    
    # Maximum nominals we can buy is the minimum of order book and ARS balance
    max_nominals_buy = min(max_nominals_buy_orderbook, max_nominals_buy_by_ars)
    
    # Calculate USD we can purchase (what we receive from selling dollar bond in step 2)
    dollar_buy_price_original = arbitrage_info['dollar_buy_price_original']
    dollar_buy_proceeds_per_nominal = dollar_buy_price_original * (1 - MARKET_FEE_RATE)  # We receive less due to fees
    max_usd_purchase = max_nominals_buy * dollar_buy_proceeds_per_nominal
    
    # Also need to verify USD balance constraint for step 3
    # After step 2, we'll have: initial_usd + (nominals * dollar_buy_proceeds_per_nominal)
    # For step 3, we need: nominals * dollar_sell_cost_per_nominal (with fees)
    dollar_sell_cost_per_nominal = dollar_sell_price_original * (1 + MARKET_FEE_RATE)  # We pay more due to fees
    usd_needed_per_nominal = dollar_sell_cost_per_nominal - dollar_buy_proceeds_per_nominal
    
    if usd_needed_per_nominal > 0:
        # We need additional USD balance
        if initial_usd < 0:
            # Negative balance: can't proceed
            max_usd_purchase = 0
        else:
            # Calculate max nominals based on USD balance
            # We need: initial_usd >= nominals * usd_needed_per_nominal
            max_nominals_by_usd = int(initial_usd / usd_needed_per_nominal)
            max_usd_purchase_by_usd = max_nominals_by_usd * dollar_buy_proceeds_per_nominal
            max_usd_purchase = min(max_usd_purchase, max_usd_purchase_by_usd)
    else:
        # dollar_sell_cost <= dollar_buy_proceeds, so step 2 provides enough USD for step 3
        # No additional USD balance needed
        pass
    
    # Final volume: min(max_usd_purchase, max_usd_sell)
    max_fx_volume_usd = min(max_usd_purchase, max_usd_sell)
    
    if max_fx_volume_usd <= 0:
        print(f"[ARBITRAGE] Opportunity detected but insufficient volume or balance")
        print(f"  Buy Pair: {arbitrage_info['buy_pair_name']}, Sell Pair: {arbitrage_info['sell_pair_name']}")
        print(f"  Potential Profit (after fees): {arbitrage_info['arbitrage_profit_pct']:.4f}%")
        print(f"  Max USD purchase (steps 1-2): {max_usd_purchase:,.2f}")
        print(f"  Max USD sell (steps 3-4): {max_usd_sell:,.2f}")
        print(f"  Available ARS balance: {initial_ars:,.2f}")
        print(f"  Available USD balance: {initial_usd:,.2f}")
        print(f"  Skipping trade execution")
        return False
    
    # Calculate actual nominals based on the limiting USD volume
    # Use the purchase side to determine nominals (since that's what we can afford)
    if max_fx_volume_usd == max_usd_purchase:
        # Limited by purchase capacity
        actual_nominals = max_nominals_buy
    else:
        # Limited by sell capacity
        actual_nominals = max_nominals_sell
    
    # Ensure we don't exceed the other constraint
    actual_nominals = min(actual_nominals, max_nominals_buy, max_nominals_sell)
    
    if actual_nominals <= 0:
        print(f"[ARBITRAGE] Opportunity detected but insufficient volume or balance")
        print(f"  Buy Pair: {arbitrage_info['buy_pair_name']}, Sell Pair: {arbitrage_info['sell_pair_name']}")
        print(f"  Potential Profit (after fees): {arbitrage_info['arbitrage_profit_pct']:.4f}%")
        print(f"  Max USD purchase: {max_usd_purchase:,.2f}")
        print(f"  Max USD sell: {max_usd_sell:,.2f}")
        print(f"  Calculated nominals: {actual_nominals}")
        print(f"  Skipping trade execution")
        return False
    
    # Execute the trade with calculated nominals
    # Note: Balances will be updated by execute_trade() for each trade using original prices + fees
    trade_result = execute_arbitrage_trade(order_books, actual_nominals, arbitrage_info)
    
    # Print trade details
    print(f"\n{'='*60}")
    print(f"ARBITRAGE OPPORTUNITY DETECTED at {timestamp}")
    print(f"{'='*60}")
    print(f"Buy Pair: {arbitrage_info['buy_pair_name']}")
    print(f"Sell Pair: {arbitrage_info['sell_pair_name']}")
    
    # Detailed FX calculation breakdown
    print(f"\n{'─'*60}")
    print(f"IMPLICIT FX CALCULATION DETAILS:")
    print(f"{'─'*60}")
    
    # FX Buy calculation
    print(f"\nFX Buy (after fees): {arbitrage_info['implicit_fx_buy']:.4f} ARS/USD")
    print(f"  To buy USD via {arbitrage_info['buy_pair_name']}:")
    print(f"    Buy {arbitrage_info['peso_buy_security']}:")
    print(f"      Price (original): {arbitrage_info['peso_buy_price_original']:.2f} ARS")
    print(f"      Price (with fees): {arbitrage_info['peso_buy_price']:.2f} ARS")
    print(f"      Available volume: {arbitrage_info['peso_buy_volume']:.2f} nominals")
    print(f"    Sell {arbitrage_info['dollar_buy_security']}:")
    print(f"      Price (original): {arbitrage_info['dollar_buy_price_original']:.2f} USD")
    print(f"      Price (with fees): {arbitrage_info['dollar_buy_price']:.2f} USD")
    print(f"      Available volume: {arbitrage_info['dollar_buy_volume']:.2f} nominals")
    print(f"    Calculation: {arbitrage_info['peso_buy_price']:.2f} / {arbitrage_info['dollar_buy_price']:.2f} = {arbitrage_info['implicit_fx_buy']:.4f}")
    
    # FX Sell calculation
    print(f"\nFX Sell (after fees): {arbitrage_info['implicit_fx_sell']:.4f} ARS/USD")
    print(f"  To sell USD via {arbitrage_info['sell_pair_name']}:")
    print(f"    Buy {arbitrage_info['dollar_sell_security']}:")
    print(f"      Price (original): {arbitrage_info['dollar_sell_price_original']:.2f} USD")
    print(f"      Price (with fees): {arbitrage_info['dollar_sell_price']:.2f} USD")
    print(f"      Available volume: {arbitrage_info['dollar_sell_volume']:.2f} nominals")
    print(f"    Sell {arbitrage_info['peso_sell_security']}:")
    print(f"      Price (original): {arbitrage_info['peso_sell_price_original']:.2f} ARS")
    print(f"      Price (with fees): {arbitrage_info['peso_sell_price']:.2f} ARS")
    print(f"      Available volume: {arbitrage_info['peso_sell_volume']:.2f} nominals")
    print(f"    Calculation: {arbitrage_info['peso_sell_price']:.2f} / {arbitrage_info['dollar_sell_price']:.2f} = {arbitrage_info['implicit_fx_sell']:.4f}")
    
    print(f"\nArbitrage Profit (after fees): {arbitrage_info['arbitrage_profit_pct']:.4f}%")
    print(f"\nTrade Execution:")
    print(f"  FX Volume (dollars): {trade_result['volume']:.2f}")
    print(f"  Nominals: {trade_result['nominals']}")
    print(f"  Peso Buy Cost (pesos, with fees): {trade_result['peso_buy_cost']:.2f}")
    print(f"  Dollar Buy Proceeds (dollars, with fees): {trade_result['dollar_buy_proceeds']:.2f}")
    print(f"  Dollar Sell Cost (dollars, with fees): {trade_result['dollar_sell_cost']:.2f}")
    print(f"  Peso Sell Proceeds (pesos, with fees): {trade_result['peso_sell_proceeds']:.2f}")
    print(f"  Net Profit (pesos, after fees): {trade_result['net_profit_pesos']:.2f}")
    print(f"  Return (after fees): {trade_result['return_pct']:.4f}%")
    print(f"\nBalance Changes:")
    print(f"  ARS: {initial_ars:,.2f} -> {ars_balance['balance']:,.2f} (change: {ars_balance['balance'] - initial_ars:+,.2f})")
    print(f"  USD: {initial_usd:,.2f} -> {usd_balance['balance']:,.2f} (change: {usd_balance['balance'] - initial_usd:+,.2f})")
    if usd_balance['balance'] < 0:
        print(f"  WARNING: USD balance is negative! {usd_balance['balance']:.2f}")
        # interrupt code execution
        exit()


    print(f"{'='*60}")
    
    # Execute 4 trades by sending orders to market via FIX
    # Each trade is executed separately
    # Use original prices (market execution prices) for trade execution
    nominals = trade_result['nominals']
    
    # Trade 1: Buy peso bond (buy pair) - buy from offers (is_bid=False)
    # This will spend ARS (price + fees) - balances updated in execute_trade()
    execute_trade(
        arbitrage_info['peso_buy_security'],
        arbitrage_info['peso_buy_price_original'],
        nominals,
        timestamp,
        order_book=order_books[arbitrage_info['peso_buy_security']],
        is_bid=False,
        ars_balance=ars_balance,
        usd_balance=usd_balance
    )
    
    # Trade 2: Sell dollar bond (buy pair) - sell to bids (is_bid=True)
    # This will receive USD (price - fees) - balances updated in execute_trade()
    execute_trade(
        arbitrage_info['dollar_buy_security'],
        arbitrage_info['dollar_buy_price_original'],
        nominals,
        timestamp,
        order_book=order_books[arbitrage_info['dollar_buy_security']],
        is_bid=True,
        ars_balance=ars_balance,
        usd_balance=usd_balance
    )
    
    # Trade 3: Buy dollar bond (sell pair) - buy from offers (is_bid=False)
    # This will spend USD (price + fees) - balances updated in execute_trade()
    execute_trade(
        arbitrage_info['dollar_sell_security'],
        arbitrage_info['dollar_sell_price_original'],
        nominals,
        timestamp,
        order_book=order_books[arbitrage_info['dollar_sell_security']],
        is_bid=False,
        ars_balance=ars_balance,
        usd_balance=usd_balance
    )
    
    # Trade 4: Sell peso bond (sell pair) - sell to bids (is_bid=True)
    # This will receive ARS (price - fees) - balances updated in execute_trade()
    execute_trade(
        arbitrage_info['peso_sell_security'],
        arbitrage_info['peso_sell_price_original'],
        nominals,
        timestamp,
        order_book=order_books[arbitrage_info['peso_sell_security']],
        is_bid=True,
        ars_balance=ars_balance,
        usd_balance=usd_balance
    )
    
    return True
