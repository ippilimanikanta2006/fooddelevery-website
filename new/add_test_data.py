from app import app
from models import db, User, MenuItem

def add_second_restaurant():
    with app.app_context():
        # Add a second restaurant owner
        if not User.query.filter_by(username="burger_king").first():
            bk = User(username="burger_king", role="restaurant_owner", phone="1122334455", address="Food Court, Mall Road")
            bk.set_password("password")
            db.session.add(bk)
            db.session.commit()
            
            # Add items for this restaurant
            items = [
                MenuItem(name="Whopper", price=199.0, description="Signature flame-grilled beef patty burger.", user_id=bk.id),
                MenuItem(name="Crispy Chicken Burger", price=149.0, description="Crispy chicken fillet with mayo and lettuce.", user_id=bk.id),
                MenuItem(name="French Fries", price=99.0, description="Golden and crispy salted fries.", user_id=bk.id),
                MenuItem(name="Onion Rings", price=119.0, description="Breaded and fried onion rings.", user_id=bk.id),
            ]
            db.session.add_all(items)
            db.session.commit()
            print("✓ Added Burger King and its menu items.")
        else:
            print("! Burger King already exists.")

if __name__ == "__main__":
    add_second_restaurant()
