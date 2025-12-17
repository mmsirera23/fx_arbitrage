"""
Module for FX market data processing and order book maintenance.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Optional, Tuple

from orderbook import OrderBook
from strategy import execute_strategy, ARBITRAGE_SECURITIES

def read_market_data(file_path: str) -> pd.DataFrame:
    """
    Read a CSV file with market data and return a DataFrame.
    
    Args:
        file_path: Path to the CSV file
        
    Returns:
        DataFrame with parsed market data
    """
    df = pd.read_csv(file_path)
    
    # Convert time column to datetime
    df['time'] = pd.to_datetime(df['time'])
    
    # Sort by time
    df = df.sort_values('time')
    
    return df


def update_order_book(order_book: OrderBook, row: pd.Series) -> None:
    """
    Update the order book with a new row of market data.
    
    Args:
        order_book: OrderBook instance to update
        row: DataFrame row with market data
    """
    # Extract bid prices and quantities
    bid_prices = [
        float(row['BI_price_1']), float(row['BI_price_2']), float(row['BI_price_3']),
        float(row['BI_price_4']), float(row['BI_price_5'])
    ]
    bid_quantities = [
        float(row['BI_quantity_1']), float(row['BI_quantity_2']), float(row['BI_quantity_3']),
        float(row['BI_quantity_4']), float(row['BI_quantity_5'])
    ]
    
    # Extract offer prices and quantities
    offer_prices = [
        float(row['OF_price_1']), float(row['OF_price_2']), float(row['OF_price_3']),
        float(row['OF_price_4']), float(row['OF_price_5'])
    ]
    offer_quantities = [
        float(row['OF_quantity_1']), float(row['OF_quantity_2']), float(row['OF_quantity_3']),
        float(row['OF_quantity_4']), float(row['OF_quantity_5'])
    ]
    
    # Update the order book
    order_book.update_bids(bid_prices, bid_quantities)
    order_book.update_offers(offer_prices, offer_quantities)
    # Convert pandas Timestamp to Python datetime
    time_value = row['time']
    if hasattr(time_value, 'to_pydatetime'):
        order_book.last_update_time = time_value.to_pydatetime()  # type: ignore
    else:
        order_book.last_update_time = time_value  # type: ignore


def calculate_implicit_fx(order_book: OrderBook) -> Dict[str, Optional[Tuple[float, float]]]:
    """
    Calculate implicit FX rates from the order book.
    Returns the highest (best bid) and lowest (best offer) implicit FX rates
    with their available volumes.
    
    Args:
        order_book: OrderBook instance to query
        
    Returns:
        Dictionary with:
            - 'highest_fx': Tuple (price, volume) of best bid (highest implicit FX)
            - 'lowest_fx': Tuple (price, volume) of best offer (lowest implicit FX)
        Returns None for values if that side of the book is empty
    """
    best_bid = order_book.get_best_bid()
    best_offer = order_book.get_best_offer()
    
    return {
        'highest_fx': best_bid,  # Highest price = best bid
        'lowest_fx': best_offer   # Lowest price = best offer
    }

def process_market_data_updates(
    all_data: pd.DataFrame, 
    order_books: Dict[str, OrderBook],
    ars_balance: Dict[str, float],
    usd_balance: Dict[str, float]
) -> None:
    """
    Process all market data updates in chronological order.
    After each market update, executes all arbitrage opportunities iteratively
    before processing the next market update.
    
    Args:
        all_data: DataFrame with all market data sorted by timestamp
        order_books: Dictionary of order books by security
        ars_balance: Dictionary with ARS balance (will be updated)
        usd_balance: Dictionary with USD balance (will be updated)
    """
    print(f"Processing {len(all_data)} market data updates in chronological order")
    
    # Queue to store pending market updates while executing strategy
    pending_updates = []
    strategy_executing = False
    
    # Process each row in chronological order
    for idx, row in all_data.iterrows():
        security = str(row['security'])
        timestamp = pd.to_datetime(row['time'])
        
        # If strategy is executing, queue this update instead of processing it
        if strategy_executing:
            pending_updates.append((idx, row))
            continue
        
        # Create order book if it doesn't exist
        if security not in order_books:
            order_books[security] = OrderBook(security)
        
        # Update order book with the new market data
        update_order_book(order_books[security], row)
        
        # Set flag to indicate we're executing strategy
        # This will cause subsequent market updates to be queued
        strategy_executing = True
        
        # After updating the order book, check for arbitrage opportunities
        # Execute all possible opportunities iteratively until no more exist
        # This will execute the 4-trade strategy multiple times if opportunities persist
        from strategy import execute_arbitrage_opportunities_iteratively
        opportunities_executed = execute_arbitrage_opportunities_iteratively(
            order_books, timestamp, ars_balance, usd_balance
        )
        
        # Strategy execution complete, clear the flag
        strategy_executing = False
        
        # Process any pending updates that were queued during strategy execution
        # First, apply all pending updates to the order books (without checking for opportunities)
        # These updates were ignored while we were executing the strategy
        while pending_updates:
            pending_idx, pending_row = pending_updates.pop(0)
            pending_security = str(pending_row['security'])
            
            # Create order book if it doesn't exist
            if pending_security not in order_books:
                order_books[pending_security] = OrderBook(pending_security)
            
            # Update order book with the queued market data
            update_order_book(order_books[pending_security], pending_row)
        
        # After processing all pending updates, check for new opportunities
        # This handles the case where our trades or the pending updates created new opportunities
        # Use the timestamp of the current market update
        from strategy import execute_arbitrage_opportunities_iteratively
        opportunities_executed = execute_arbitrage_opportunities_iteratively(
            order_books, timestamp, ars_balance, usd_balance
        )
    
    print(f"  - Processed {len(all_data)} updates")
    print(f"  - Securities found: {list(order_books.keys())}")

def run(data_dir: str = "data", initial_balance: float = 0.0) -> Tuple[Dict[str, OrderBook], float, float]:
    """
    Main function that processes all data files and updates the order books.
    Processes all market data updates in chronological order by timestamp.
    
    Args:
        data_dir: Directory containing CSV data files
        initial_balance: Initial balance in ARS
        
    Returns:
        Tuple (order_books, final_ars_balance, final_usd_balance)
    """
    data_path = Path(data_dir)
    
    if not data_path.exists():
        raise FileNotFoundError(f"Directory {data_dir} does not exist")
    
    # Dictionary to maintain order books by security
    order_books: Dict[str, OrderBook] = {}
    
    # Initialize balances
    ars_balance = {'balance': initial_balance}
    usd_balance = {'balance': 0.0}
    
    # Find CSV files in the directory
    csv_files = sorted(data_path.glob("*.csv"))
    
    if not csv_files:
        print(f"No CSV files found in {data_dir}")
        return order_books, ars_balance['balance'], usd_balance['balance']
    
    
    # Read all files and combine into a single DataFrame
    all_dataframes = []
    for csv_file in csv_files:
        try:
            df = read_market_data(str(csv_file))
            all_dataframes.append(df)
            print(f"  - Loaded {csv_file.name} with {len(df)} rows")
        except Exception as e:
            print(f"Error loading {csv_file}: {e}")
    
    if not all_dataframes:
        print("No data loaded")
        return order_books, ars_balance['balance'], usd_balance['balance']
    
    # Combine all DataFrames
    all_data = pd.concat(all_dataframes, ignore_index=True)
    print(f"\nTotal rows loaded: {len(all_data)}")
    
    # Sort by timestamp to process in chronological order
    print("Sorting data by timestamp...")
    all_data = all_data.sort_values('time').reset_index(drop=True)
    
    print("-" * 60)
    print(f"Initial Balance: ARS {ars_balance['balance']:,.2f}, USD {usd_balance['balance']:,.2f}")
    print("-" * 60)
    
    # Process all updates in chronological order
    process_market_data_updates(all_data, order_books, ars_balance, usd_balance)
    
    print("-" * 60)
    print(f"\nProcessing completed.")
    print(f"Total securities processed: {len(order_books)}")
    
    # Show order books summary
    print("\nOrder Books Summary:")
    for security, ob in order_books.items():
        print(f"  {ob}")
    
    return order_books, ars_balance['balance'], usd_balance['balance']

if __name__ == "__main__":

    INITIAL_BALANCE = 500_000_000
    # Execute processing
    order_books, final_ars_balance, final_usd_balance = run(initial_balance=INITIAL_BALANCE)
    
    # Log final balances
    print("\n" + "=" * 60)
    print("FINAL BALANCES")
    print("=" * 60)
    print(f"ARS Balance: {final_ars_balance:,.2f}")
    print(f"USD Balance: {final_usd_balance:,.2f}")
    print(f"Initial ARS Balance: {INITIAL_BALANCE:,.2f}")
    print(f"Net Change ARS: {final_ars_balance - INITIAL_BALANCE:,.2f}")
    print("=" * 60)
    
    # Hardcoded security pairs available for FX arbitrage
    # These are the 4 instruments: AL30 (pesos), AL30D (dollars), GD30 (pesos), GD30D (dollars)
    arbitrage_securities = ARBITRAGE_SECURITIES
    
    # Create array of pairs that can interact for arbitrage
    arbitrage_pairs = []
    pair_names = list(arbitrage_securities.keys())
    
    # Generate all combinations of pairs (each pair can interact with any other pair)
    for i, pair1_name in enumerate(pair_names):
        for pair2_name in pair_names[i+1:]:
            arbitrage_pairs.append({
                'pair1': pair1_name,
                'pair1_peso': arbitrage_securities[pair1_name]['peso_security'],
                'pair1_dollar': arbitrage_securities[pair1_name]['dollar_security'],
                'pair2': pair2_name,
                'pair2_peso': arbitrage_securities[pair2_name]['peso_security'],
                'pair2_dollar': arbitrage_securities[pair2_name]['dollar_security']
            })
    
    print("\n" + "=" * 60)
    print("Arbitrage Securities Available:")
    print("=" * 60)
    print(f"Total bond pairs: {len(arbitrage_securities)}")
    print(f"Total arbitrage combinations: {len(arbitrage_pairs)}")
    print("\nBond Pairs:")
    for pair_name, securities in arbitrage_securities.items():
        print(f"  {pair_name}:")
        print(f"    Peso: {securities['peso_security']}")
        print(f"    Dollar: {securities['dollar_security']}")
    
    print("\nArbitrage Combinations:")
    for combo in arbitrage_pairs:
        print(f"  {combo['pair1']} <-> {combo['pair2']}")
        print(f"    Direction 1: Buy USD via {combo['pair1']}, Sell USD via {combo['pair2']}")
        print(f"    Direction 2: Buy USD via {combo['pair2']}, Sell USD via {combo['pair1']}")
    


