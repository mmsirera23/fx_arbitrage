"""
Module for FX market data processing and order book maintenance.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Optional, Tuple

from orderbook import OrderBook

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


def execute_strategy(order_book: OrderBook, timestamp) -> None:
    """
    Execute the trading strategy.
    
    Args:
        order_book: OrderBook instance to analyze
        timestamp: Current timestamp of the market data update
    """
    print("Strategy executed")
    print(order_book, " - ", timestamp)
    
    # Calculate implicit FX rates
    implicit_fx = calculate_implicit_fx(order_book)
    print(f"  Highest FX (Best Bid): {implicit_fx['highest_fx']}")
    print(f"  Lowest FX (Best Offer): {implicit_fx['lowest_fx']}")


def process_market_data_updates(all_data: pd.DataFrame, order_books: Dict[str, OrderBook]) -> None:
    """
    Process all market data updates in chronological order.
    
    Args:
        all_data: DataFrame with all market data sorted by timestamp
        order_books: Dictionary of order books by security
    """
    print(f"Processing {len(all_data)} market data updates in chronological order")
    
    # Process each row in chronological order
    for idx, row in all_data.iterrows():
        security = str(row['security'])
        timestamp = pd.to_datetime(row['time'])
        
        # Create order book if it doesn't exist
        if security not in order_books:
            order_books[security] = OrderBook(security)
        
        # Update order book with the new market data
        update_order_book(order_books[security], row)
        
        # Execute strategy after updating the order book
        execute_strategy(order_books[security], timestamp)
    
    print(f"  - Processed {len(all_data)} updates")
    print(f"  - Securities found: {list(order_books.keys())}")


def run(data_dir: str = "data") -> Dict[str, OrderBook]:
    """
    Main function that processes all data files and updates the order books.
    Processes all market data updates in chronological order by timestamp.
    
    Args:
        data_dir: Directory containing CSV data files
        
    Returns:
        Dictionary with updated order books by security
    """
    data_path = Path(data_dir)
    
    if not data_path.exists():
        raise FileNotFoundError(f"Directory {data_dir} does not exist")
    
    # Dictionary to maintain order books by security
    order_books: Dict[str, OrderBook] = {}
    
    # Find CSV files in the directory
    csv_files = sorted(data_path.glob("*.csv"))
    
    if not csv_files:
        print(f"No CSV files found in {data_dir}")
        return order_books
    
    print(f"Found {len(csv_files)} CSV files")
    print("-" * 60)
    
    # Read all files and combine into a single DataFrame
    all_dataframes = []
    for csv_file in csv_files:
        try:
            print(f"Loading file: {csv_file.name}")
            df = read_market_data(str(csv_file))
            all_dataframes.append(df)
            print(f"  - Loaded {len(df)} rows")
        except Exception as e:
            print(f"Error loading {csv_file}: {e}")
    
    if not all_dataframes:
        print("No data loaded")
        return order_books
    
    # Combine all DataFrames
    all_data = pd.concat(all_dataframes, ignore_index=True)
    print(f"\nTotal rows loaded: {len(all_data)}")
    
    # Sort by timestamp to process in chronological order
    print("Sorting data by timestamp...")
    all_data = all_data.sort_values('time').reset_index(drop=True)
    
    print("-" * 60)
    
    # Process all updates in chronological order
    process_market_data_updates(all_data, order_books)
    
    print("-" * 60)
    print(f"\nProcessing completed.")
    print(f"Total securities processed: {len(order_books)}")
    
    # Show order books summary
    print("\nOrder Books Summary:")
    for security, ob in order_books.items():
        print(f"  {ob}")
    
    return order_books


if __name__ == "__main__":
    # Execute processing
    order_books = run()
    
    # Example usage: show statistics
    if order_books:
        print("\n" + "=" * 60)
        print("Final Statistics:")
        print("=" * 60)
        
        for security, ob in order_books.items():
            best_bid = ob.get_best_bid()
            best_offer = ob.get_best_offer()
            spread = ob.get_spread()
            
            print(f"\nSecurity: {security}")
            print(f"  Best Bid: {best_bid}")
            print(f"  Best Offer: {best_offer}")
            print(f"  Spread: {spread}")
            print(f"  Bid Levels: {len(ob.bids)}")
            print(f"  Offer Levels: {len(ob.offers)}")
            print(f"  Last Update: {ob.last_update_time}")

