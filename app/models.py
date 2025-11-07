from flask_sqlalchemy import SQLAlchemy#, ForeignKey
from datetime import datetime, timezone

# Create the SQLAlchemy instance
db = SQLAlchemy()

# Define your TestTable model
class WatchlistTable(db.Model):
    __tablename__ = 'watchlist'
    
    id = db.Column(db.Integer, primary_key=True)
    #watchlist_id = db.Column(db.Integer, ForeignKey('user_made_watchlists.id'), nullable=False)  # Foreign key to user-made watchlist
    ticker = db.Column(db.String(10), nullable=False)  # varchar column
    position = db.Column(db.Integer, default=0)  # position of stock column
    
    def __init__(self, ticker):
        self.ticker = ticker
        if self.position is None:
            # If no position specified, add to the end
            last_item = WatchlistTable.query.order_by(WatchlistTable.position.desc()).first()
            self.position = 1 if last_item is None else last_item.position + 1
        else:
            self.position = self.position
    
    def __repr__(self):
        return f'<Watchlist {self.ticker}>'

class TopMoversCache(db.Model):
    __tablename__ = 'top_movers_cache'
    
    id = db.Column(db.Integer, primary_key=True)
    period = db.Column(db.String(10), nullable=False)  # e.g., '1d', '1mo'
    data = db.Column(db.JSON, nullable=False)  # Store the top movers data as JSON
    last_updated = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    
    
    def __repr__(self):
        return f'<TopMoversCache {self.period}>'

#class UserMadeWatchlistTable(db.Model):
#    __tablename__ = 'user_made_watchlists'
#
#    id = db.Column(db.Integer, primary_key=True)
#    watchlist_name = db.Column(db.String(100), nullable=False, unique=True)  # Unique name for the watchlist
#    watchlists = db.relationship('WatchlistTable', backref='user_made_watchlists', cascade='all, delete')
    
  