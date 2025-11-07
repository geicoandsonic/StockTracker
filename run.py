from app import create_app
from app.models import db

app = create_app() #From __init__.py 

with app.app_context():
    db.create_all()  # This creates the tables in the database
    print("Database tables created!")

if __name__ == '__main__':
    app.run(debug=True)
