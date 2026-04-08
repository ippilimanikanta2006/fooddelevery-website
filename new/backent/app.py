import os
from flask import Flask, render_template, redirect, url_for, request, flash, session, abort
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from models import db, User, MenuItem, Order
from datetime import datetime, timezone, timedelta

# ---------------------------------------------------------------------------
# App configuration
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-key-for-local-use-only")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///food_delivery.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

# Configure upload folder for menu item images
UPLOAD_FOLDER = os.path.join("static", "images")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ---------------------------------------------------------------------------
# Helper – owner-only decorator
# ---------------------------------------------------------------------------
def owner_required(func):
    from functools import wraps

    @wraps(func)
    @login_required
    def wrapper(*args, **kwargs):
        if current_user.role != "restaurant_owner":
            abort(403)
        return func(*args, **kwargs)

    return wrapper


# ---------------------------------------------------------------------------
# Routes – Authentication
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    if current_user.is_authenticated:
        if current_user.role == "restaurant_owner":
            return redirect(url_for("admin_orders"))
        return redirect(url_for("menu"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user)
            flash("Logged in successfully!", "success")
            if user.role == "restaurant_owner":
                return redirect(url_for("admin_orders"))
            return redirect(url_for("menu"))

        flash("Invalid username or password.", "danger")

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        phone = request.form.get("phone", "").strip()
        role = request.form.get("role", "customer")  # Capture role

        if User.query.filter_by(username=username).first():
            flash("Username already taken.", "warning")
            return redirect(url_for("register"))

        user = User(username=username, role=role, phone=phone)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        login_user(user)
        flash("Account created! Welcome!", "success")
        return redirect(url_for("menu"))

    return render_template("register.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Routes – Customer
# ---------------------------------------------------------------------------
@app.route("/menu")
@login_required
def menu():
    items = MenuItem.query.all()
    cart = session.get("cart", {})
    return render_template("menu.html", items=items, cart=cart)


@app.route("/add-to-cart/<int:item_id>", methods=["POST"])
@login_required
def add_to_cart(item_id):
    item = MenuItem.query.get_or_404(item_id)
    cart = session.get("cart", {})
    key = str(item_id)
    cart[key] = cart.get(key, 0) + 1
    session["cart"] = cart
    flash(f"{item.name} added to cart!", "success")
    return redirect(url_for("menu"))


@app.route("/remove-from-cart/<int:item_id>", methods=["POST"])
@login_required
def remove_from_cart(item_id):
    item = MenuItem.query.get_or_404(item_id)
    cart = session.get("cart", {})
    key = str(item_id)
    if key in cart:
        cart[key] -= 1
        if cart[key] <= 0:
            del cart[key]
    session["cart"] = cart
    flash("Item removed from cart.", "info")
    return redirect(url_for("menu"))


@app.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    cart = session.get("cart", {})
    if not cart:
        flash("Your cart is empty.", "warning")
        return redirect(url_for("menu"))

    # Build a list of (MenuItem, qty) for display
    cart_items = []
    total = 0.0
    for item_id_str, qty in cart.items():
        item = MenuItem.query.get(int(item_id_str))
        if item:
            cart_items.append((item, qty))
            total += item.price * qty

    if request.method == "POST":
        block = request.form.get("delivery_address", "").strip()
        room_sel = request.form.get("room_number", "").strip()
        
        if room_sel == "Other":
            room_val = request.form.get("other_room", "").strip()
        else:
            room_val = room_sel
            
        final_address = f"{block}, Room {room_val}"
        
        if not block or not room_val:
            flash("Please enter a delivery address.", "danger")
            return render_template("checkout.html", cart_items=cart_items, total=total)

        # Build items summary
        summary_parts = [f"{item.name} x{qty}" for item, qty in cart_items]
        items_summary = ", ".join(summary_parts)

        order = Order(
            user_id=current_user.id,
            items_summary=items_summary,
            total_price=round(total, 2),
            delivery_address=final_address,
        )
        db.session.add(order)
        db.session.commit()

        session.pop("cart", None)
        flash("Order placed successfully!", "success")
        return redirect(url_for("my_orders"))

    return render_template("checkout.html", cart_items=cart_items, total=total)


@app.route("/my-orders")
@login_required
def my_orders():
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.id.desc()).all()
    return render_template("my_orders.html", orders=orders)


# ---------------------------------------------------------------------------
# Routes – Admin (Restaurant Owner)
# ---------------------------------------------------------------------------
@app.route("/admin/orders")
@owner_required
def admin_orders():
    orders = Order.query.order_by(Order.id.desc()).all()
    
    # Calculate daily collection (successful transactions today)
    today = datetime.now(timezone.utc).date()
    # We filter by 'Delivered' or 'Confirmed' as 'successful'
    successful_orders_today = Order.query.filter(
        Order.created_at >= datetime.combine(today, datetime.min.time()),
        Order.status.in_(['Confirmed', 'Delivered'])
    ).all()
    
    daily_total = sum(order.total_price for order in successful_orders_today)
    
    return render_template("admin_orders.html", orders=orders, daily_total=daily_total)


@app.route("/admin/orders/<int:order_id>/update-status", methods=["POST"])
@owner_required
def update_order_status(order_id):
    order = Order.query.get_or_404(order_id)
    new_status = request.form.get("status", "").strip()
    allowed = {"Confirmed", "Rejected", "Delivered"}
    if new_status not in allowed:
        flash("Invalid status.", "danger")
        return redirect(url_for("admin_orders"))

    order.status = new_status
    db.session.commit()
    flash(f"Order #{order.id} marked as {new_status}.", "success")
    return redirect(url_for("admin_orders"))


@app.route("/admin/menu")
@owner_required
def admin_menu():
    items = MenuItem.query.all()
    return render_template("admin_menu.html", items=items)


@app.route("/admin/menu/edit/<int:item_id>", methods=["GET", "POST"])
@owner_required
def edit_menu_item(item_id):
    item = MenuItem.query.get_or_404(item_id)
    
    if request.method == "POST":
        name = request.form.get("name")
        price = request.form.get("price")
        description = request.form.get("description")
        
        if not name or not price:
            flash("Name and price are required.", "danger")
            return redirect(url_for("edit_menu_item", item_id=item_id))
            
        item.name = name
        item.price = float(price)
        item.description = description
        
        # Handle image upload
        if "image" in request.files:
            file = request.files["image"]
            if file and file.filename != "" and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                # Add timestamp to avoid cache/overlap
                filename = f"{int(datetime.now().timestamp())}_{filename}"
                file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
                item.image_filename = filename
                
        db.session.commit()
        flash(f"Menu item '{item.name}' updated successfully!", "success")
        return redirect(url_for("admin_menu"))
        
    return render_template("edit_menu_item.html", item=item)


@app.route("/admin/menu/delete/<int:item_id>", methods=["POST"])
@owner_required
def delete_menu_item(item_id):
    item = MenuItem.query.get_or_404(item_id)
    name = item.name
    
    # Optional: Delete the image file if it exists and isn't shared
    if item.image_filename:
        image_path = os.path.join(app.config["UPLOAD_FOLDER"], item.image_filename)
        if os.path.exists(image_path):
            try:
                os.remove(image_path)
            except Exception as e:
                print(f"Error deleting image file: {e}")
                
    db.session.delete(item)
    db.session.commit()
    
    flash(f"Menu item '{name}' has been deleted.", "warning")
    return redirect(url_for("admin_menu"))


@app.route("/admin/menu/add", methods=["GET", "POST"])
@owner_required
def add_menu_item():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        price = request.form.get("price", "0.0")
        description = request.form.get("description", "").strip()
        file = request.files.get("image")

        if not name or not price:
            flash("Name and price are required.", "danger")
            return redirect(url_for("add_menu_item"))

        filename = None
        if file and allowed_file(file.filename):

            filename = secure_filename(file.filename)
            # To avoid collisions, we could prefix with a timestamp or UUID
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

        item = MenuItem(
            name=name,
            price=float(price),
            description=description,
            image_filename=filename
        )
        db.session.add(item)
        db.session.commit()
        flash("Menu item added successfully!", "success")
        return redirect(url_for("menu"))

    return render_template("add_menu_item.html")


# ---------------------------------------------------------------------------
# Database seeding
# ---------------------------------------------------------------------------
def seed_database():
    """Create owner account & sample menu items if DB is empty."""
    if User.query.first() is not None:
        return  # already seeded

    # Restaurant owner
    owner = User(username="owner", role="restaurant_owner", phone="9876543210")
    owner.set_password("password")
    db.session.add(owner)

    # Sample customer
    customer = User(username="customer1", role="customer", phone="1234567890")
    customer.set_password("password")
    db.session.add(customer)

    # Menu items
    items = [
        MenuItem(name="Margherita Pizza", price=299.0, description="Classic cheese & tomato pizza with fresh basil.", image_filename="margherita_pizza.png"),
        MenuItem(name="Butter Chicken", price=349.0, description="Creamy tomato-based curry with tender chicken.", image_filename="butter_chicken.png"),
        MenuItem(name="Veg Biryani", price=249.0, description="Fragrant basmati rice with mixed vegetables & spices.", image_filename="veg_biryani.png"),
        MenuItem(name="Paneer Tikka", price=279.0, description="Smoky grilled cottage cheese with bell peppers.", image_filename="paneer_tikka.png"),
        MenuItem(name="Chicken Burger", price=199.0, description="Juicy chicken patty with lettuce, cheese & mayo.", image_filename="chicken_burger.png"),
        MenuItem(name="Masala Dosa", price=149.0, description="Crispy rice crepe stuffed with spiced potato filling.", image_filename="masala_dosa.png"),
        MenuItem(name="Chocolate Brownie", price=129.0, description="Rich, fudgy brownie topped with chocolate ganache.", image_filename=None),
        MenuItem(name="Mango Lassi", price=99.0, description="Chilled yogurt drink blended with ripe mango.", image_filename=None),
    ]
    db.session.add_all(items)
    db.session.commit()
    print("✓ Database seeded with owner, customer, and 8 menu items.")


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        seed_database()
    app.run(debug=True, port=5000)
