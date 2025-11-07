from flask import render_template, request, jsonify, redirect, url_for, flash
import yfinance as yf
import pandas as pd
import requests as requests
from datetime import datetime, timezone, timedelta
from app.models import db, WatchlistTable, TopMoversCache
from app import top_movers_cache  # Import the in-memory cache
from io import StringIO

# Global variable for cache (will be set by app/__init__.py)
top_movers_cache = {}
# Global variable to store full historical data
historical_data_cache = {}
# Timestamp of last full data download
last_full_data_update = None

def get_top_movers(market='sp500', limit=10, period=None):
    """Get top movers for a specific period using cached historical data"""
    global historical_data_cache, last_full_data_update
    
    if period is None:
        period = request.args.get('period', '1mo')
    
    # Get the list of stocks based on the market
    stock_list = get_stock_list(market)
    
    # Check if we need to download new data (once per day or if cache is empty)
    current_time = datetime.now()
    if (historical_data_cache.get(market) is None or 
        last_full_data_update is None or 
        (current_time - last_full_data_update).total_seconds() > 86400):  # 24 hours
        
        # Download fresh data
        historical_data_cache[market] = download_full_historical_data(stock_list)
        last_full_data_update = current_time
        print(f"Updated historical data cache at {last_full_data_update}")
    
    # Calculate period-specific metrics from the full dataset
    results = calculate_period_data(historical_data_cache[market], period)
    
    # Sort results
    results.sort(key=lambda x: x['change_percent'], reverse=True)
    
    # Get top gainers and losers
    gainers = results[:limit]
    losers = results[-limit:] if len(results) >= limit else []
    losers.reverse()  # So the biggest losers come first
    
    return {
        'gainers': gainers,
        'losers': losers
    }

def get_stock_list(market):
    if market == 'sp500':
        # Get S&P 500 components with proper headers to avoid 403 error
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        try:
            url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
            response = requests.get(url, headers=headers)
            response.raise_for_status()  # Raise an exception for bad status codes
            
            # Use StringIO to convert the response text to a file-like object for pandas
            sp500 = pd.read_html(StringIO(response.text))[0]
            return sp500['Symbol'].tolist()
        except Exception as e:
            print(f"Error fetching S&P 500 data: {str(e)}")
            # Fallback to a hardcoded list or alternative source
            return get_fallback_sp500_list()
            
    elif market == 'nasdaq100':
        # Get NASDAQ-100 components with proper headers
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        try:
            url = 'https://en.wikipedia.org/wiki/Nasdaq-100'
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            nasdaq100 = pd.read_html(StringIO(response.text))[1] 
            return nasdaq100['Ticker'].tolist()
        except Exception as e:
            print(f"Error fetching NASDAQ-100 data: {str(e)}")
            return get_fallback_nasdaq100_list()
    
    # Add more markets as needed
    return []

def get_fallback_sp500_list():
    """Fallback list of major S&P 500 stocks in case Wikipedia is unavailable"""
    return [
        'AAPL', 'MSFT', 'AMZN', 'NVDA', 'GOOGL', 'GOOG', 'META', 'TSLA', 'UNH', 'JNJ',
        'JPM', 'V', 'PG', 'XOM', 'HD', 'CVX', 'MA', 'PFE', 'ABBV', 'BAC',
        'COST', 'DIS', 'KO', 'ADBE', 'WMT', 'CRM', 'MRK', 'PEP', 'TMO', 'NFLX',
        'ABT', 'ORCL', 'ACN', 'NKE', 'LLY', 'DHR', 'TXN', 'NEE', 'VZ', 'AMD',
        'RTX', 'QCOM', 'LOW', 'PM', 'UPS', 'HON', 'SPGI', 'COP', 'INTU', 'IBM'
    ]

def get_fallback_nasdaq100_list():
    """Fallback list of major NASDAQ-100 stocks"""
    return [
        'AAPL', 'MSFT', 'AMZN', 'NVDA', 'GOOGL', 'GOOG', 'META', 'TSLA', 'AVGO', 'COST',
        'NFLX', 'ADBE', 'PEP', 'TMUS', 'CSCO', 'INTC', 'PYPL', 'CMCSA', 'TXN', 'AMGN',
        'HON', 'QCOM', 'SBUX', 'INTU', 'AMD', 'ISRG', 'BKNG', 'AMAT', 'ADI', 'GILD',
        'MU', 'ADP', 'LRCX', 'MELI', 'MDLZ', 'REGN', 'KLAC', 'SNPS', 'CDNS', 'MAR'
    ]

def download_full_historical_data(stock_list):
    """Download 10 year historical data for all stocks at once"""
    print(f"Downloading historical data for {len(stock_list)} stocks...")
    # Use the longest period available to get complete data
    data = yf.download(stock_list, period="max", group_by='ticker', auto_adjust=True)
    print("Download complete!")
    return data

def calculate_period_data(full_data, period):
    """Calculate percentage changes for a specific period using the full dataset"""
    # Define cutoff dates based on period
    now = datetime.now()
    if period == '1d':
        cutoff = now - timedelta(days=1)
    elif period == '5d':
        cutoff = now - timedelta(days=5)
    elif period == '1mo':
        cutoff = now - timedelta(days=30)
    elif period == '3mo':
        cutoff = now - timedelta(days=90)
    elif period == '6mo':
        cutoff = now - timedelta(days=180)
    elif period == 'ytd':
        cutoff = datetime(now.year, 1, 1)
    elif period == '1y':
        cutoff = now - timedelta(days=365)
    elif period == '2y':
        cutoff = now - timedelta(days=730)
    elif period == '5y':
        cutoff = now - timedelta(days=1825)
    elif period == '10y':
        cutoff = now - timedelta(days=3650)
    else:
        cutoff = now - timedelta(days=30)  # Default to 1 month
    
    # Convert cutoff to pandas timestamp
    cutoff = pd.Timestamp(cutoff)
    
    results = []
    stocks_without_data = []
    
    # Process each stock
    stocks_to_process = full_data.columns.levels[0] if isinstance(full_data.columns, pd.MultiIndex) else [None]
    print(f"Processing {len(stocks_to_process)} stocks for period {period}")
    
    for stock in stocks_to_process:
        try:
            # Get stock data
            if stock:
                stock_data = full_data[stock]
            else:
                stock_data = full_data  # Single stock case
                
            # Filter data from cutoff date
            filtered_data = stock_data[stock_data.index >= cutoff]
            
            if filtered_data.empty:
                stocks_without_data.append(stock if stock else "Unknown")
                continue  # Skip if no data for this period
            
            if len(filtered_data) < 2:
                stocks_without_data.append(stock if stock else "Unknown")
                continue  # Need at least two data points to calculate change
            
            # Calculate percentage change
            first_price = filtered_data['Close'].iloc[0]
            last_price = filtered_data['Close'].iloc[-1]

             # Skip if either price is NaN or zero
            if pd.isna(first_price) or pd.isna(last_price) or first_price == 0:
                stocks_without_data.append(stock if stock else "Unknown")
                continue

            change_percent = ((last_price - first_price) / first_price) * 100
            
            results.append({
                'symbol': stock if stock else full_data.columns.levels[0][0],
                'change_percent': change_percent,
                'start_price': float(first_price),  # Convert to float for JSON serialization
                'end_price': float(last_price)
            })
        except Exception as e:
            print(f"Error processing {stock} for period {period}: {str(e)}")
    
    print(f"For period {period}: found data for {len(results)} stocks, missing data for {len(stocks_without_data)} stocks")
    if not results:
        print(f"WARNING: No results for period {period}!")
    
    return results

def configure_routes(app):

    @app.route('/watchlist')
    def watchlist():
        # Get all stocks from watchlist, ordered by position
        watchlist_stocks = WatchlistTable.query.order_by(WatchlistTable.position).all()
    
        # Extract just the ticker symbols for the template
        stocks = [stock.ticker for stock in watchlist_stocks]
    
        # Pass to template
        return render_template('watchlist.html', stocks=stocks)  

    #Add create watchlist here to allow users to create different watchlists
    #@app.route('/create-watchlist')
    #def create_watchlist():

    @app.route('/add-to-watchlist', methods=['POST'])
    def add_to_watchlist():
        # Get the stock ticker from the form
        ticker = request.form.get('ticker', '')
        
        # Validate that the ticker is real
        if ticker:
            ticker = ticker.strip().upper()  # Clean up the ticker input
            # Check if the ticker is valid by trying to fetch data from yfinance
            try:
                stock_ticker = yf.Ticker(ticker)
                stock_info = stock_ticker.info
            except Exception as ex:
                flash(f"'{ticker}' is not a valid ticker symbol.", "error")                
                return redirect(url_for('watchlist'))
             
            #Check if the ticker already exists in the watchlist
            existing = WatchlistTable.query.filter_by(ticker=ticker).first()
            if not existing:
                add_to_watchlist_helper(ticker)
            else:
                print(f"Ticker {ticker} already in watchlist.")

        # Redirect back to watchlist
        return redirect(url_for('watchlist'))

    @app.route('/add-to-watchlist/<ticker>')
    def add_to_watchlist_in_top_movers(ticker):
        add_to_watchlist_helper(ticker)
        # Redirect back to watchlist
        flash(f"'{ticker}' added to your watchlist.","success")   
        return redirect(url_for('top_movers'))

    # Helper function to add a stock to the watchlist
    def add_to_watchlist_helper(stock_ticker):
        try:
            # Create a new WatchlistTable entry
            new_stock = WatchlistTable(ticker=stock_ticker)
            db.session.add(new_stock)
            db.session.commit()
        except Exception as e:
            db.session.rollback()  # Roll back the transaction if there's an error
            print(f"Error adding {stock_ticker} to watchlist: {str(e)}")
            flash(f"Couldn't add {stock_ticker} to watchlist. Please try again later.", "error")

    @app.route('/remove-from-watchlist/<ticker>')
    def remove_from_watchlist(ticker):

        #Search for the stock in the watchlist
        ticker = WatchlistTable.query.filter_by(ticker=ticker).first()
        if ticker:
            db.session.delete(ticker)
            db.session.commit()
        else:
            print(f"Ticker {ticker} not found in watchlist.")
        # Redirect back to watchlist
        return redirect(url_for('watchlist'))

    @app.route('/move-watchlist/<ticker>/<direction>')
    def move_watchlist_item(ticker, direction):
        stock_ticker = WatchlistTable.query.filter_by(ticker=ticker).first()

        if not stock_ticker:
            flash(f"Ticker '{ticker}' not found in watchlist.", "error")
            return redirect(url_for('watchlist'))

        if direction == 'up':
            new_stock_placement = WatchlistTable.query.filter_by(position=stock_ticker.position - 1).first()

        if direction == 'down':
            new_stock_placement = WatchlistTable.query.filter_by(position=stock_ticker.position + 1).first()

        if new_stock_placement:
            # Swap positions
            temp_position = stock_ticker.position
            stock_ticker.position = new_stock_placement.position
            new_stock_placement.position = temp_position
            db.session.commit()

        return redirect(url_for('watchlist'))

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/dashboard')
    def dashboard():

        # Get the selected period from the request
        period = request.args.get('period', '1mo')

        # Get the selected sorting method from the request
        sorter = request.args.get('sorter', 'Position')

        match sorter:
            case 'Largest Change':
                all_stocks = WatchlistTable.query.order_by(WatchlistTable.position).all()
                watchlist_symbols = [item.ticker for item in all_stocks]
                yf_stocks = yf.download(watchlist_symbols, period=period, group_by='ticker', auto_adjust=True)
                watchlist_stocks = largest_change(yf_stocks, period)
            case 'Smallest Change':
                all_stocks = WatchlistTable.query.order_by(WatchlistTable.position).all()
                watchlist_symbols = [item.ticker for item in all_stocks]
                yf_stocks = yf.download(watchlist_symbols, period=period, group_by='ticker', auto_adjust=True)
                watchlist_stocks = smallest_change(yf_stocks, period)
            case 'Position':
                all_stocks = WatchlistTable.query.order_by(WatchlistTable.position).all()
                watchlist_stocks = [stock.ticker for stock in all_stocks]
            case 'Alphabetical':
                all_stocks = WatchlistTable.query.order_by(WatchlistTable.ticker).all()
                watchlist_stocks = [stock.ticker for stock in all_stocks]
            case _:
                all_stocks = WatchlistTable.query.order_by(WatchlistTable.position).all()
                watchlist_stocks = [stock.ticker for stock in all_stocks]
       
        #watchlist_stocks = WatchlistTable.query.order_by(WatchlistTable.position).all()
        # Extract just the ticker symbols for the template
        #stocks = [stock.ticker for stock in watchlist_stocks]

        # If no valid stocks provided, use defaults
        if not watchlist_stocks:
            watchlist_stocks = ['AAPL', 'MSFT', 'GOOGL']

        #Once we have gotten the stocks, Flask takes the list and passes it to the "dashboard.html" template
        # Once there, it goes through each stock (in the for each stock loop) and fetches the data for each stock
        return render_template('dashboard.html', stocks=watchlist_stocks, sorter=sorter, period=period)

    def largest_change(stocks, period):
        results = calculate_period_data(stocks, period)
        # Sort results by change_percent in descending order
        results.sort(key=lambda x: x['change_percent'], reverse=True)
        # Extract and return just the symbols
        return [stock['symbol'] for stock in results]

    def smallest_change(stocks, period):
        results = calculate_period_data(stocks, period)
        # Sort results by change_percent in descending order
        results.sort(key=lambda x: x['change_percent'], reverse=False)
        # Extract and return just the symbols
        return [stock['symbol'] for stock in results]

    @app.route('/top-movers')
    def top_movers():
        period = request.args.get('period', '1mo')
        # Get the current user's watchlist from database
        watchlist_stocks = WatchlistTable.query.order_by(WatchlistTable.position).all()
    
        # Extract just the symbols from watchlist items into a simple list
        watchlist_symbols = [item.ticker for item in watchlist_stocks]
    
        # Get cached data for rendering the template
        if period in top_movers_cache:
            movers = top_movers_cache[period]
        else:
            # Fall back to fetching data if not cached
            movers = get_top_movers(period=period)
        
        # Pass both gainers and losers to the template
        return render_template('top-movers.html', 
                               stocks=[stock['symbol'] for stock in movers['gainers'] + movers['losers']],
                               watchlist_symbols=watchlist_symbols,
                               period=period)

    # This method gets a list of top movers based on the provided market and period.
    # Only the top limit # are returned, both as the greatest gainers and the greatest losers.
    @app.route('/api/top-movers')
    def api_top_movers():
        period = request.args.get('period', '1mo')
        
        # Check if we have cached data
        if period in top_movers_cache:
            return jsonify(top_movers_cache[period])
        
       # If not in memory cache, check database
        cache_entry = TopMoversCache.query.filter_by(period=period).first()
        if cache_entry:
            # Make sure we're comparing timezone-aware datetimes
            now = datetime.now(timezone.utc)
            
            # Make sure last_updated is timezone-aware
            last_updated = cache_entry.last_updated
            if last_updated.tzinfo is None:
                # If it's naive for some reason, make it aware
                last_updated = last_updated.replace(tzinfo=timezone.utc)
            
            # Compare with explicit timezone awareness
            if now - last_updated < timedelta(hours=1):
                # Update in-memory cache
                top_movers_cache[period] = cache_entry.data
                return jsonify(cache_entry.data)
        
        
        # If no cache or cache too old, get fresh data
        movers = get_top_movers(period=period)
        return jsonify(movers)     

    @app.route('/api/stock-data')
    def get_stock_data():
        symbol = request.args.get('symbol', 'AAPL')
        period = request.args.get('period', '1mo')

        try:
            # Fetch stock data
            stock = yf.Ticker(symbol)
            hist = stock.history(period=period)
            #print(stock.info)
            if hist.empty:
                return jsonify({
                    'symbol': symbol,
                    'error': 'No data available for this symbol'
                }), 404
            
            # Process data for front-end visualization
            dates = hist.index.strftime('%Y-%m-%d').tolist()
            prices = hist['Close'].tolist()
            
            return jsonify({
                'name': stock.info.get('shortName', symbol),
                'symbol': symbol,
                'dates': dates,
                'prices': prices
            })
            
        except Exception as e:
            # Log the error (in a production app)
            print(f"Error fetching data for {symbol}: {str(e)}")
            return jsonify({
                'symbol': symbol,
                'error': str(e)
            }), 500