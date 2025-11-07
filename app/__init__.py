from flask import Flask
from app.models import db, WatchlistTable, TopMoversCache  # Import the db instance and models
from config import Config
from datetime import datetime, timezone
import threading # Import threading for background tasks (like caching the S&P 500 stocks for top movers)
import time
import json

# Dictionary to store cached data in memory
top_movers_cache = {}

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)  # Load configuration

    # Initialize the database with the app
    db.init_app(app)

    # Import and register blueprints/routes
    from app.routes import configure_routes
    configure_routes(app) # In routes.py, this function sets up the routes for the app
    
     # Create a function to create the database tables
    @app.before_first_request
    def create_tables():
        db.create_all()

     # Load any existing cached data into memory
        with app.app_context():
            cache_entries = TopMoversCache.query.all()
            for entry in cache_entries:
                top_movers_cache[entry.period] = entry.data
    
    # Start the background thread for preloading data
    threading.Thread(target=preload_top_movers, args=(app,), daemon=True).start()
    return app

def preload_top_movers(app):
    """Background thread to preload and update top movers data"""
    with app.app_context():
        from app.routes import get_top_movers
        periods = ['1d', '5d', '1mo', '3mo', '6mo', 'ytd', '1y', '2y', '5y', '10y']
        
        # First download will happen when the first calculation is requested
        
        while True:
            try:
                print("Updating top movers cache...")
                # Process all periods using the cached historical data
                for period in periods:
                    # Get data for this period
                    movers_data = get_top_movers(period=period)
                    
                    # Update memory cache
                    top_movers_cache[period] = movers_data
                    
                    # Update database cache
                    cache_entry = TopMoversCache.query.filter_by(period=period).first()
                    if cache_entry:
                        cache_entry.data = movers_data
                        cache_entry.last_updated = datetime.now(timezone.utc)
                    else:
                        new_cache = TopMoversCache(period=period, data=movers_data)
                        db.session.add(new_cache)
                    
                    db.session.commit()
                
                print("Top movers cache updated successfully")
                # Wait before updating again - shorter interval since calculations are faster now
                time.sleep(3600)  # Update every hour
            except Exception as e:
                print(f"Error updating top movers cache: {str(e)}")
                time.sleep(300)  # If error, try