from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import os
from twilio.rest import Client
from dotenv import load_dotenv
import logging
from datetime import datetime

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Database setup
def init_db():
    conn = sqlite3.connect('treehouse.db')
    c = conn.cursor()
    
    # Enhanced users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number TEXT UNIQUE NOT NULL,
            name TEXT,
            email TEXT,
            dorm_building TEXT,
            room_number TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Menus table
    c.execute('''
        CREATE TABLE IF NOT EXISTS menus (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            restaurant_name TEXT NOT NULL,
            menu_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Menu items table
    c.execute('''
        CREATE TABLE IF NOT EXISTS menu_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            menu_id INTEGER NOT NULL,
            item_name TEXT NOT NULL,
            description TEXT,
            price DECIMAL(10,2) NOT NULL,
            category TEXT,
            image_path TEXT,
            is_available BOOLEAN DEFAULT 1,
            FOREIGN KEY (menu_id) REFERENCES menus (id)
        )
    ''')
    
    # Orders table
    c.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            total_amount DECIMAL(10,2) NOT NULL,
            delivery_fee DECIMAL(5,2) NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            scheduled_delivery_time TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Order items table
    c.execute('''
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            menu_item_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            item_price DECIMAL(10,2) NOT NULL,
            special_instructions TEXT,
            FOREIGN KEY (order_id) REFERENCES orders (id),
            FOREIGN KEY (menu_item_id) REFERENCES menu_items (id)
        )
    ''')
    
    # Payments table
    c.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            amount DECIMAL(10,2) NOT NULL,
            payment_method TEXT NOT NULL,
            transaction_id TEXT,
            status TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (order_id) REFERENCES orders (id)
        )
    ''')
    
    # Delivery batches table
    c.execute('''
        CREATE TABLE IF NOT EXISTS delivery_batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            delivery_time TIMESTAMP NOT NULL,
            status TEXT NOT NULL DEFAULT 'scheduled',
            driver_name TEXT,
            driver_phone TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Batch orders (join table)
    c.execute('''
        CREATE TABLE IF NOT EXISTS batch_orders (
            batch_id INTEGER NOT NULL,
            order_id INTEGER NOT NULL,
            PRIMARY KEY (batch_id, order_id),
            FOREIGN KEY (batch_id) REFERENCES delivery_batches (id),
            FOREIGN KEY (order_id) REFERENCES orders (id)
        )
    ''')
    
    conn.commit()
    conn.close()

# Initialize the database when the app starts
init_db()

# Twilio setup
account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')
twilio_phone = os.getenv('TWILIO_PHONE_NUMBER')
notification_email = os.getenv('NOTIFICATION_EMAIL')

client = None
if account_sid and auth_token:
    try:
        client = Client(account_sid, auth_token)
        logger.info("Twilio client initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing Twilio client: {e}")
else:
    logger.warning("Twilio credentials not found or incomplete")

@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.json
    phone_number = data.get('phone_number')
    name = data.get('name')
    email = data.get('email')
    dorm_building = data.get('dorm_building')
    room_number = data.get('room_number')
    
    if not phone_number:
        return jsonify({"error": "Phone number is required"}), 400
    
    # Clean the phone number - remove any non-digit characters
    clean_phone = ''.join(filter(str.isdigit, phone_number))
    
    # Add to database
    try:
        conn = sqlite3.connect('treehouse.db')
        c = conn.cursor()
        
        # Check if user already exists
        c.execute("SELECT id FROM users WHERE phone_number = ?", (clean_phone,))
        user = c.fetchone()
        
        if user:
            # Update existing user if more info provided
            if any([name, email, dorm_building, room_number]):
                query = "UPDATE users SET "
                params = []
                
                if name:
                    query += "name = ?, "
                    params.append(name)
                if email:
                    query += "email = ?, "
                    params.append(email)
                if dorm_building:
                    query += "dorm_building = ?, "
                    params.append(dorm_building)
                if room_number:
                    query += "room_number = ?, "
                    params.append(room_number)
                
                # Remove the trailing comma and space
                query = query.rstrip(", ")
                query += " WHERE phone_number = ?"
                params.append(clean_phone)
                
                c.execute(query, params)
                conn.commit()
                is_new_user = False
                user_id = user[0]
            else:
                is_new_user = False
                user_id = user[0]
        else:
            # Insert new user
            c.execute(
                "INSERT INTO users (phone_number, name, email, dorm_building, room_number) VALUES (?, ?, ?, ?, ?)",
                (clean_phone, name, email, dorm_building, room_number)
            )
            user_id = c.lastrowid
            is_new_user = True
        
        conn.commit()
        conn.close()
        
        # Send notification via Twilio if it's a new user
        if is_new_user and client:
            try:
                message = client.messages.create(
                    body=f"New TreeHouse signup! Phone: {phone_number}",
                    from_=twilio_phone,
                    to=notification_email
                )
                logger.info(f"Notification sent: {message.sid}")
            except Exception as e:
                logger.error(f"Error sending notification: {e}")
        
        return jsonify({
            "success": True, 
            "message": "Sign-up successful!",
            "user_id": user_id
        }), 200
    except Exception as e:
        logger.error(f"Database error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/menus', methods=['GET'])
def get_menus():
    try:
        conn = sqlite3.connect('treehouse.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM menus")
        menus = [dict(row) for row in c.fetchall()]
        conn.close()
        
        if not menus:
            # Fallback to dummy data if no menus in database
            dummy_menus = [
                {"id": 1, "restaurant_name": "Chipotle", "menu_path": "/menus/chipotle.pdf"},
                {"id": 2, "restaurant_name": "Starbucks", "menu_path": "/menus/starbucks.pdf"},
                {"id": 3, "restaurant_name": "Subway", "menu_path": "/menus/subway.pdf"}
            ]
            return jsonify({"menus": dummy_menus}), 200
        
        return jsonify({"menus": menus}), 200
    except Exception as e:
        logger.error(f"Database error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/menu-items', methods=['GET'])
def get_menu_items():
    restaurant_id = request.args.get('restaurant_id')
    
    try:
        conn = sqlite3.connect('treehouse.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        if restaurant_id:
            c.execute("SELECT * FROM menu_items WHERE menu_id = ?", (restaurant_id,))
        else:
            c.execute("SELECT * FROM menu_items")
            
        items = [dict(row) for row in c.fetchall()]
        conn.close()
        
        return jsonify({"menu_items": items}), 200
    except Exception as e:
        logger.error(f"Database error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/orders', methods=['POST'])
def create_order():
    data = request.json
    user_id = data.get('user_id')
    items = data.get('items')
    delivery_fee = data.get('delivery_fee', 2.00)
    scheduled_time = data.get('scheduled_time')
    
    if not user_id or not items:
        return jsonify({"error": "User ID and items are required"}), 400
    
    try:
        conn = sqlite3.connect('treehouse.db')
        c = conn.cursor()
        
        # Calculate total amount
        total_amount = float(delivery_fee)
        for item in items:
            item_id = item.get('menu_item_id')
            quantity = item.get('quantity', 1)
            
            c.execute("SELECT price FROM menu_items WHERE id = ?", (item_id,))
            result = c.fetchone()
            if not result:
                conn.close()
                return jsonify({"error": f"Menu item {item_id} not found"}), 404
                
            item_price = float(result[0])
            total_amount += item_price * quantity
        
        # Create order
        c.execute(
            "INSERT INTO orders (user_id, total_amount, delivery_fee, scheduled_delivery_time) VALUES (?, ?, ?, ?)",
            (user_id, total_amount, delivery_fee, scheduled_time)
        )
        order_id = c.lastrowid
        
        # Add order items
        for item in items:
            item_id = item.get('menu_item_id')
            quantity = item.get('quantity', 1)
            special_instructions = item.get('special_instructions', '')
            
            c.execute("SELECT price FROM menu_items WHERE id = ?", (item_id,))
            item_price = float(c.fetchone()[0])
            
            c.execute(
                "INSERT INTO order_items (order_id, menu_item_id, quantity, item_price, special_instructions) VALUES (?, ?, ?, ?, ?)",
                (order_id, item_id, quantity, item_price, special_instructions)
            )
        
        # Find the appropriate delivery batch based on scheduled time
        if scheduled_time:
            c.execute(
                "SELECT id FROM delivery_batches WHERE delivery_time = ? AND status = 'scheduled'",
                (scheduled_time,)
            )
            batch_result = c.fetchone()
            batch_id = None
            
            if batch_result:
                batch_id = batch_result[0]
            else:
                # Create a new batch if one doesn't exist
                c.execute(
                    "INSERT INTO delivery_batches (delivery_time, status) VALUES (?, 'scheduled')",
                    (scheduled_time,)
                )
                batch_id = c.lastrowid
            
            # Add order to batch
            c.execute(
                "INSERT INTO batch_orders (batch_id, order_id) VALUES (?, ?)",
                (batch_id, order_id)
            )
        
        conn.commit()
        
        # Send notification via Twilio
        if client:
            try:
                # Get user info for notification
                c.execute("SELECT phone_number FROM users WHERE id = ?", (user_id,))
                user_result = c.fetchone()
                user_phone = user_result[0] if user_result else "Unknown"
                
                message = client.messages.create(
                    body=f"New TreeHouse order! Order ID: {order_id}, Amount: ${total_amount:.2f}, User: {user_phone}",
                    from_=twilio_phone,
                    to=notification_email
                )
                logger.info(f"Order notification sent: {message.sid}")
            except Exception as e:
                logger.error(f"Error sending order notification: {e}")
        
        conn.close()
        return jsonify({
            "success": True,
            "message": "Order created successfully!",
            "order_id": order_id,
            "total_amount": total_amount
        }), 201
    except Exception as e:
        logger.error(f"Database error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/orders', methods=['GET'])
def get_orders():
    user_id = request.args.get('user_id')
    
    try:
        conn = sqlite3.connect('treehouse.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        if user_id:
            c.execute("""
                SELECT o.*, 
                       (SELECT COUNT(*) FROM order_items WHERE order_id = o.id) as item_count 
                FROM orders o 
                WHERE o.user_id = ? 
                ORDER BY o.created_at DESC
            """, (user_id,))
        else:
            c.execute("""
                SELECT o.*, 
                       (SELECT COUNT(*) FROM order_items WHERE order_id = o.id) as item_count 
                FROM orders o 
                ORDER BY o.created_at DESC
            """)
            
        orders = [dict(row) for row in c.fetchall()]
        conn.close()
        
        return jsonify({"orders": orders}), 200
    except Exception as e:
        logger.error(f"Database error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/orders/<int:order_id>', methods=['GET'])
def get_order_details(order_id):
    try:
        conn = sqlite3.connect('treehouse.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # Get order details
        c.execute("""
            SELECT o.*, u.phone_number, u.name, u.dorm_building, u.room_number
            FROM orders o
            JOIN users u ON o.user_id = u.id
            WHERE o.id = ?
        """, (order_id,))
        order = dict(c.fetchone() or {})
        
        if not order:
            conn.close()
            return jsonify({"error": "Order not found"}), 404
        
        # Get order items
        c.execute("""
            SELECT oi.*, mi.item_name, mi.description
            FROM order_items oi
            JOIN menu_items mi ON oi.menu_item_id = mi.id
            WHERE oi.order_id = ?
        """, (order_id,))
        items = [dict(row) for row in c.fetchall()]
        
        # Get payment info
        c.execute("SELECT * FROM payments WHERE order_id = ?", (order_id,))
        payment = dict(c.fetchone() or {})
        
        # Get delivery batch info
        c.execute("""
            SELECT db.*
            FROM delivery_batches db
            JOIN batch_orders bo ON db.id = bo.batch_id
            WHERE bo.order_id = ?
        """, (order_id,))
        batch = dict(c.fetchone() or {})
        
        conn.close()
        
        result = {
            "order": order,
            "items": items,
            "payment": payment,
            "delivery_batch": batch
        }
        
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Database error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/payments', methods=['POST'])
def process_payment():
    data = request.json
    order_id = data.get('order_id')
    amount = data.get('amount')
    payment_method = data.get('payment_method')
    transaction_id = data.get('transaction_id')
    
    if not order_id or not amount or not payment_method:
        return jsonify({"error": "Order ID, amount, and payment method are required"}), 400
    
    try:
        conn = sqlite3.connect('treehouse.db')
        c = conn.cursor()
        
        # Check if order exists
        c.execute("SELECT id, total_amount, user_id FROM orders WHERE id = ?", (order_id,))
        order = c.fetchone()
        
        if not order:
            conn.close()
            return jsonify({"error": "Order not found"}), 404
        
        # Ensure payment amount matches order total
        order_total = float(order[1])
        payment_amount = float(amount)
        
        if payment_amount < order_total:
            conn.close()
            return jsonify({"error": f"Payment amount (${payment_amount:.2f}) is less than order total (${order_total:.2f})"}), 400
        
        # Record payment
        c.execute(
            "INSERT INTO payments (order_id, amount, payment_method, transaction_id, status) VALUES (?, ?, ?, ?, 'completed')",
            (order_id, amount, payment_method, transaction_id)
        )
        payment_id = c.lastrowid
        
        # Update order status
        c.execute("UPDATE orders SET status = 'paid' WHERE id = ?", (order_id,))
        
        conn.commit()
        
        # Send notification via Twilio
        if client:
            try:
                # Get user info for notification
                user_id = order[2]
                c.execute("SELECT phone_number FROM users WHERE id = ?", (user_id,))
                user_result = c.fetchone()
                user_phone = user_result[0] if user_result else "Unknown"
                
                message = client.messages.create(
                    body=f"Payment received! Order ID: {order_id}, Amount: ${payment_amount:.2f}, User: {user_phone}",
                    from_=twilio_phone,
                    to=notification_email
                )
                logger.info(f"Payment notification sent: {message.sid}")
            except Exception as e:
                logger.error(f"Error sending payment notification: {e}")
        
        conn.close()
        
        return jsonify({
            "success": True,
            "message": "Payment processed successfully!",
            "payment_id": payment_id
        }), 200
    except Exception as e:
        logger.error(f"Database error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/delivery-batches', methods=['GET'])
def get_delivery_batches():
    date = request.args.get('date')
    status = request.args.get('status')
    
    try:
        conn = sqlite3.connect('treehouse.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        query = "SELECT * FROM delivery_batches WHERE 1=1"
        params = []
        
        if date:
            query += " AND DATE(delivery_time) = DATE(?)"
            params.append(date)
        
        if status:
            query += " AND status = ?"
            params.append(status)
            
        query += " ORDER BY delivery_time"
        
        c.execute(query, params)
        batches = [dict(row) for row in c.fetchall()]
        
        # For each batch, get the count of orders
        for batch in batches:
            c.execute("""
                SELECT COUNT(*) 
                FROM batch_orders 
                WHERE batch_id = ?
            """, (batch['id'],))
            batch['order_count'] = c.fetchone()[0]
        
        conn.close()
        
        return jsonify({"delivery_batches": batches}), 200
    except Exception as e:
        logger.error(f"Database error: {e}")
        return jsonify({"error": str(e)}), 500

# Route to initialize some sample data (for testing)
@app.route('/api/init-sample-data', methods=['POST'])
def init_sample_data():
    try:
        conn = sqlite3.connect('treehouse.db')
        c = conn.cursor()
        
        # Add sample restaurants and menus
        restaurants = [
            ("Chipotle", "/menus/chipotle.pdf"),
            ("Starbucks", "/menus/starbucks.pdf"),
            ("Subway", "/menus/subway.pdf")
        ]
        
        for restaurant in restaurants:
            c.execute("INSERT OR IGNORE INTO menus (restaurant_name, menu_path) VALUES (?, ?)", restaurant)
        
        # Get restaurant IDs
        c.execute("SELECT id, restaurant_name FROM menus")
        menu_ids = {name: id for id, name in c.fetchall()}
        
        # Add menu items for Chipotle
        if "Chipotle" in menu_ids:
            chipotle_items = [
                (menu_ids["Chipotle"], "Burrito Bowl", "Rice, beans, protein, and toppings of your choice", 9.95, "Entrees"),
                (menu_ids["Chipotle"], "Burrito", "Flour tortilla filled with rice, beans, protein, and toppings", 9.95, "Entrees"),
                (menu_ids["Chipotle"], "Tacos", "Three soft or hard shell tacos with your choice of fillings", 9.95, "Entrees"),
                (menu_ids["Chipotle"], "Guacamole", "Fresh avocado, lime, cilantro", 2.45, "Sides"),
                (menu_ids["Chipotle"], "Chips", "Freshly fried and seasoned with lime and salt", 1.95, "Sides")
            ]
            
            for item in chipotle_items:
                c.execute("""
                    INSERT OR IGNORE INTO menu_items 
                    (menu_id, item_name, description, price, category) 
                    VALUES (?, ?, ?, ?, ?)
                """, item)
        
        # Add menu items for Starbucks
        if "Starbucks" in menu_ids:
            starbucks_items = [
                (menu_ids["Starbucks"], "Caramel Macchiato", "Espresso with vanilla syrup, milk and caramel drizzle", 4.95, "Hot Drinks"),
                (menu_ids["Starbucks"], "Iced Coffee", "Cold brewed coffee served over ice", 3.45, "Cold Drinks"),
                (menu_ids["Starbucks"], "Chocolate Croissant", "Buttery croissant with chocolate pieces", 3.25, "Bakery"),
                (menu_ids["Starbucks"], "Bacon & Gouda Sandwich", "Bacon and gouda cheese on an artisan roll", 4.75, "Food")
            ]
            
            for item in starbucks_items:
                c.execute("""
                    INSERT OR IGNORE INTO menu_items 
                    (menu_id, item_name, description, price, category) 
                    VALUES (?, ?, ?, ?, ?)
                """, item)
        
        # Add menu items for Subway
        if "Subway" in menu_ids:
            subway_items = [
                (menu_ids["Subway"], "Italian BMT", "Genoa salami, spicy pepperoni, and Black Forest ham", 6.99, "Footlong"),
                (menu_ids["Subway"], "Turkey Breast", "Sliced turkey breast with your choice of toppings", 6.79, "Footlong"),
                (menu_ids["Subway"], "Veggie Delite", "Lettuce, tomatoes, green peppers, cucumbers, and onions", 5.99, "Footlong"),
                (menu_ids["Subway"], "Chocolate Chip Cookie", "Freshly baked chocolate chip cookie", 0.99, "Sides")
            ]
            
            for item in subway_items:
                c.execute("""
                    INSERT OR IGNORE INTO menu_items 
                    (menu_id, item_name, description, price, category) 
                    VALUES (?, ?, ?, ?, ?)
                """, item)
        
        conn.commit()
        conn.close()
        
        return jsonify({
            "success": True,
            "message": "Sample data initialized successfully!"
        }), 200
    except Exception as e:
        logger.error(f"Database error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)
