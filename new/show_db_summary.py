import sqlite3
import os

def check_db():
    db_path = os.path.join("instance", "food_delivery.db")
    if not os.path.exists(db_path):
        # Check root if not in instance
        db_path = "food_delivery.db"
        if not os.path.exists(db_path):
            print("Database file not found.")
            return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("="*40)
    print("      DATABASE TOTAL DATA SUMMARY")
    print("="*40)

    # Users
    cursor.execute("SELECT COUNT(*) FROM users")
    user_count = cursor.fetchone()[0]
    print(f"Total Users:        {user_count}")

    # Menu Items
    cursor.execute("SELECT COUNT(*) FROM menu_items")
    menu_count = cursor.fetchone()[0]
    print(f"Total Menu Items:   {menu_count}")

    # Orders
    cursor.execute("SELECT COUNT(*) FROM orders")
    order_count = cursor.fetchone()[0]
    print(f"Total Orders:       {order_count}")

    cursor.execute("SELECT SUM(total_price) FROM orders WHERE status IN ('Confirmed', 'Delivered')")
    total_rev = cursor.fetchone()[0] or 0.0
    print(f"Total Revenue:      ₹{total_rev:.2f}")

    print("\n" + "-"*40)
    print("      RECENT ORDERS")
    print("-"*40)
    cursor.execute("""
        SELECT orders.id, users.username, orders.total_price, orders.status, orders.delivery_address 
        FROM orders 
        JOIN users ON orders.user_id = users.id 
        ORDER BY orders.id DESC LIMIT 5
    """)
    recent = cursor.fetchall()
    if recent:
        print(f"{'ID':<4} | {'Customer':<12} | {'Total':<8} | {'Status':<10} | {'Address'}")
        for r in recent:
            print(f"{r[0]:<4} | {r[1]:<12} | ₹{r[2]:<7.2f} | {r[3]:<10} | {r[4]}")
    else:
        print("No orders found.")

    conn.close()
    print("="*40)

if __name__ == "__main__":
    check_db()
