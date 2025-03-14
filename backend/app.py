import os
from twilio.rest import Client
from dotenv import load_dotenv
import logging
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3


# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

@app.route('/menus/<path:filename>')
def serve_menu(filename):
    return send_from_directory('static/menus', filename)

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
        
        # Inside your create_order function, add this before conn.close()
        # Send detailed notification to admin
        if client:
            try:
                # Get user details
                c.execute("SELECT phone_number, name, dorm_building, room_number FROM users WHERE id = ?", (user_id,))
                user_details = c.fetchone()
                user_phone = user_details[0] if user_details else "Unknown"
                user_name = user_details[1] if user_details and user_details[1] else "Unknown"
                dorm = user_details[2] if user_details and user_details[2] else "Unknown"
                room = user_details[3] if user_details and user_details[3] else "Unknown"
                
                # Get item details
                item_details = []
                for item in items:
                    item_id = item.get('menu_item_id')
                    quantity = item.get('quantity', 1)
                    special_instructions = item.get('special_instructions', '')
                    
                    c.execute("""
                        SELECT mi.item_name, mi.price, m.restaurant_name
                        FROM menu_items mi
                        JOIN menus m ON mi.menu_id = m.id
                        WHERE mi.id = ?
                    """, (item_id,))
                    
                    item_info = c.fetchone()
                    if item_info:
                        item_details.append({
                            'name': item_info[0],
                            'price': float(item_info[1]),
                            'quantity': quantity,
                            'special': special_instructions,
                            'restaurant': item_info[2]
                        })
                
                # Build detailed notification
                admin_note = f"NEW WEBSITE ORDER #{order_id}!\n\n"
                admin_note += f"Customer: {user_name} ({user_phone})\n"
                admin_note += f"Location: {dorm}, Room {room}\n\n"
                
                # Group by restaurant
                restaurants = {}
                for item in item_details:
                    if item['restaurant'] not in restaurants:
                        restaurants[item['restaurant']] = []
                    restaurants[item['restaurant']].append(item)
                
                for restaurant, items in restaurants.items():
                    admin_note += f"--- {restaurant} ---\n"
                    for item in items:
                        admin_note += f"{item['quantity']}x {item['name']} - ${item['price'] * item['quantity']:.2f}\n"
                        if item['special']:
                            admin_note += f"  Special: {item['special']}\n"
                    admin_note += "\n"
                
                admin_note += f"Delivery fee: ${delivery_fee:.2f}\n"
                admin_note += f"Total: ${total_amount:.2f}\n"
                
                if scheduled_time:
                    # Format the scheduled time
                    from datetime import datetime
                    scheduled_dt = datetime.fromisoformat(scheduled_time.replace('Z', '+00:00'))
                    time_str = scheduled_dt.strftime("%I:%M %p on %m/%d/%Y")
                    admin_note += f"\nScheduled for: {time_str}"
                
                # Send to your notification number
                client.messages.create(
                    body=admin_note,
                    from_=twilio_phone,
                    to=notification_email  # Make sure this is your phone number
                )
                logger.info(f"Admin order notification sent for order #{order_id}")
            except Exception as e:
                logger.error(f"Error sending detailed admin notification: {e}")
        
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

@app.route('/webhook/sms', methods=['POST'])
def sms_webhook():
    # Get the incoming message details
    incoming_message = request.values.get('Body', '').strip().lower()
    from_number = request.values.get('From', '')
    
    # Clean the phone number
    clean_phone = ''.join(filter(str.isdigit, from_number))
    
    # Find user by phone number
    conn = sqlite3.connect('treehouse.db')
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE phone_number = ?", (clean_phone,))
    user = c.fetchone()
    
    if not user:
        response = "You're not registered with TreeHouse. Visit our website to sign up!"
        conn.close()
        return str(response)
    
    user_id = user[0]
    
    # Process command
    if incoming_message == 'menu':
        # Send list of restaurants
        c.execute("SELECT id, restaurant_name FROM menus")
        restaurants = c.fetchall()
        
        if not restaurants:
            response = "Sorry, no restaurants available at this time. Check back later!"
            conn.close()
            return str(response)
        
        response = "Available restaurants:\n\n"
        for idx, restaurant in enumerate(restaurants, 1):
            response += f"{idx}. {restaurant[1]}\n"
        
        response += "\nReply with the number of the restaurant to see their menu."
        
        # Send the message
        if client:
            try:
                client.messages.create(
                    body=response,
                    from_=twilio_phone,
                    to=from_number
                )
            except Exception as e:
                logger.error(f"Error sending menu message: {e}")
    
    elif incoming_message.isdigit():
        # User selected a restaurant by number
        restaurant_idx = int(incoming_message) - 1
        c.execute("SELECT id, restaurant_name FROM menus")
        restaurants = c.fetchall()
        
        if 0 <= restaurant_idx < len(restaurants):
            restaurant_id, restaurant_name = restaurants[restaurant_idx]
            
            # Get menu items
            c.execute("""
                SELECT id, item_name, description, price, category 
                FROM menu_items 
                WHERE menu_id = ? AND is_available = 1
                ORDER BY category, item_name
            """, (restaurant_id,))
            
            menu_items = c.fetchall()
            
            if not menu_items:
                response = f"Sorry, {restaurant_name} doesn't have any menu items available."
                conn.close()
                
                if client:
                    try:
                        client.messages.create(
                            body=response,
                            from_=twilio_phone,
                            to=from_number
                        )
                    except Exception as e:
                        logger.error(f"Error sending error message: {e}")
                return str(response)
            
            # Group by category
            categories = {}
            for item in menu_items:
                category = item[4] or "Other"
                if category not in categories:
                    categories[category] = []
                categories[category].append(item)
            
            response = f"{restaurant_name} Menu:\n\n"
            
            for category, items in categories.items():
                response += f"--- {category} ---\n"
                for item in items:
                    response += f"{item[0]}. {item[1]} - ${item[3]:.2f}\n"
                response += "\n"
            
            response += "To order, text: ORDER item_id,quantity,special request"
            response += "\nExample: ORDER 5,2,extra sauce"
            
            # Send the menu
            if client:
                try:
                    client.messages.create(
                        body=response,
                        from_=twilio_phone,
                        to=from_number
                    )
                except Exception as e:
                    logger.error(f"Error sending menu items: {e}")
        else:
            response = "Invalid restaurant number. Text MENU to see the list again."
            if client:
                try:
                    client.messages.create(
                        body=response,
                        from_=twilio_phone,
                        to=from_number
                    )
                except Exception as e:
                    logger.error(f"Error sending error message: {e}")
    
    elif incoming_message.startswith('order '):
        # Process order
        try:
            # Parse order command
            order_parts = incoming_message[6:].split(',', 2)
            
            if len(order_parts) < 2:
                response = "Invalid order format. Please use: ORDER item_id,quantity,special request"
                conn.close()
                
                if client:
                    try:
                        client.messages.create(
                            body=response,
                            from_=twilio_phone,
                            to=from_number
                        )
                    except Exception as e:
                        logger.error(f"Error sending format error: {e}")
                return str(response)
            
            item_id = int(order_parts[0].strip())
            quantity = int(order_parts[1].strip())
            special_request = order_parts[2].strip() if len(order_parts) > 2 else ""
            
            # Get the menu item
            c.execute("""
                SELECT mi.id, mi.item_name, mi.price, m.id as menu_id, m.restaurant_name
                FROM menu_items mi
                JOIN menus m ON mi.menu_id = m.id
                WHERE mi.id = ? AND mi.is_available = 1
            """, (item_id,))
            
            menu_item = c.fetchone()
            if not menu_item:
                response = f"Menu item with ID {item_id} not found or unavailable. Please check the menu."
                conn.close()
                
                if client:
                    try:
                        client.messages.create(
                            body=response,
                            from_=twilio_phone,
                            to=from_number
                        )
                    except Exception as e:
                        logger.error(f"Error sending item not found error: {e}")
                return str(response)
            
            # Calculate costs
            item_price = float(menu_item[2])
            subtotal = item_price * quantity
            delivery_fee = 2.00
            total = subtotal + delivery_fee
            
            # Create the order
            c.execute("""
                INSERT INTO orders (user_id, total_amount, delivery_fee, status)
                VALUES (?, ?, ?, ?)
            """, (user_id, total, delivery_fee, 'pending'))
            
            order_id = c.lastrowid
            
            # Add the order item
            c.execute("""
                INSERT INTO order_items (order_id, menu_item_id, quantity, item_price, special_instructions)
                VALUES (?, ?, ?, ?, ?)
            """, (order_id, item_id, quantity, item_price, special_request))
            
            # Commit the transaction
            conn.commit()
            
            # Get next delivery time (top of the next hour)
            from datetime import datetime, timedelta
            now = datetime.now()
            next_hour = (now.replace(microsecond=0, second=0, minute=0) + timedelta(hours=1))
            
            # Format the next delivery time
            delivery_time_str = next_hour.strftime("%I:%M %p")
            
            # Send confirmation to the customer
            response = f"Thank you for your TreeHouse order!\n\n"
            response += f"ORDER #{order_id}\n"
            response += f"{quantity}x {menu_item[1]} - ${subtotal:.2f}\n"
            if special_request:
                response += f"Special request: {special_request}\n"
            response += f"\nDelivery fee: ${delivery_fee:.2f}\n"
            response += f"Total: ${total:.2f}\n\n"
            response += f"Your order will be ready for pickup at {delivery_time_str} from your dorm host.\n"
            response += "You can pay when you receive your order."
            
            if client:
                try:
                    client.messages.create(
                        body=response,
                        from_=twilio_phone,
                        to=from_number
                    )
                except Exception as e:
                    logger.error(f"Error sending order confirmation: {e}")
            
            # Send notification to admin
            admin_notification = f"NEW TEXT ORDER #{order_id}!\n\n"
            admin_notification += f"Customer: {from_number}\n"
            admin_notification += f"Restaurant: {menu_item[4]}\n\n"
            admin_notification += f"{quantity}x {menu_item[1]} - ${subtotal:.2f}\n"
            if special_request:
                admin_notification += f"Special request: {special_request}\n"
            admin_notification += f"\nDelivery fee: ${delivery_fee:.2f}\n"
            admin_notification += f"Total: ${total:.2f}\n\n"
            admin_notification += f"Scheduled for pickup at {delivery_time_str}"
            
            if client:
                try:
                    # Send to your notification number
                    client.messages.create(
                        body=admin_notification,
                        from_=twilio_phone,
                        to=notification_email  # Make sure this is your phone number
                    )
                except Exception as e:
                    logger.error(f"Error sending admin notification: {e}")
            
        except Exception as e:
            response = f"Error processing order: {str(e)}"
            logger.error(f"Order processing error: {e}")
            if client:
                try:
                    client.messages.create(
                        body=response,
                        from_=twilio_phone,
                        to=from_number
                    )
                except Exception as e:
                    logger.error(f"Error sending error message: {e}")
    else:
        response = "Sorry, I didn't understand that command. Text MENU to see restaurant options."
        if client:
            try:
                client.messages.create(
                    body=response,
                    from_=twilio_phone,
                    to=from_number
                )
            except Exception as e:
                logger.error(f"Error sending help message: {e}")
    
    conn.close()
    return str("OK")

@app.route('/test-sms')
def test_sms_simple():
    # Test parameters
    test_message = request.args.get('message', 'menu')
    test_phone = request.args.get('phone', '+1234567890')
    
    html_response = "<h2>SMS Test Results:</h2>"
    
    # Handle message types
    conn = sqlite3.connect('treehouse.db')
    c = conn.cursor()
    
    # Extract phone number digits
    clean_phone = ''.join(filter(str.isdigit, test_phone))
    
    # Check if user exists
    c.execute("SELECT id FROM users WHERE phone_number = ?", (clean_phone,))
    user = c.fetchone()
    
    if not user:
        # Add test user if not found
        c.execute("INSERT INTO users (phone_number) VALUES (?)", (clean_phone,))
        conn.commit()
        c.execute("SELECT id FROM users WHERE phone_number = ?", (clean_phone,))
        user = c.fetchone()
        html_response += f"<p>Created new test user with phone: {test_phone}</p>"
    
    # Handle the message based on content
    if test_message.lower() == 'menu':
        # Get restaurants
        c.execute("SELECT id, restaurant_name FROM menus")
        restaurants = c.fetchall()
        
        if not restaurants:
            html_response += "<p>No restaurants available</p>"
        else:
            html_response += "<p>Available restaurants:</p><ul>"
            for idx, restaurant in enumerate(restaurants, 1):
                html_response += f"<li>{idx}. {restaurant[1]}</li>"
            html_response += "</ul>"
            html_response += "<p>Reply with a number to see the menu</p>"
    
    elif test_message.isdigit():
        restaurant_idx = int(test_message) - 1
        
        # Get restaurant
        c.execute("SELECT id, restaurant_name FROM menus")
        restaurants = c.fetchall()
        
        if 0 <= restaurant_idx < len(restaurants):
            restaurant_id, restaurant_name = restaurants[restaurant_idx]
            
            html_response += f"<h3>{restaurant_name} Menu</h3>"
            
            # Get menu items
            c.execute("""
                SELECT id, item_name, description, price, category 
                FROM menu_items 
                WHERE menu_id = ? AND is_available = 1
                ORDER BY category, item_name
            """, (restaurant_id,))
            
            menu_items = c.fetchall()
            
            if menu_items:
                # Group by category
                categories = {}
                for item in menu_items:
                    category = item[4] or "Other"
                    if category not in categories:
                        categories[category] = []
                    categories[category].append(item)
                
                # Display items by category
                for category, items in categories.items():
                    html_response += f"<h4>--- {category} ---</h4>"
                    html_response += "<ul>"
                    for item in items:
                        html_response += f"<li>ID #{item[0]}: {item[1]} - ${item[3]:.2f}<br/><small>{item[2]}</small></li>"
                    html_response += "</ul>"
                
                html_response += "<p>To order, type: <code>order item_id,quantity,special request</code><br/>Example: <code>order 1,2,extra sauce</code></p>"
            else:
                html_response += "<p>No menu items found for this restaurant</p>"
        else:
            html_response += "<p>Invalid restaurant number</p>"
    
    elif test_message.lower().startswith('order '):
        # Parse order
        html_response += "<h3>Order Processing</h3>"
        
        try:
            # Remove "order " and split by comma
            order_parts = test_message[6:].split(',')
            
            if len(order_parts) < 2:
                html_response += "<p>Invalid format. Use: ORDER item_id,quantity,special_request</p>"
            else:
                item_id = int(order_parts[0].strip())
                quantity = int(order_parts[1].strip())
                special_request = order_parts[2].strip() if len(order_parts) > 2 else ""
                
                # Get item details
                c.execute("""
                    SELECT mi.item_name, mi.price, m.restaurant_name
                    FROM menu_items mi
                    JOIN menus m ON mi.menu_id = m.id
                    WHERE mi.id = ?
                """, (item_id,))
                
                item = c.fetchone()
                
                if item:
                    # Create order
                    item_name, price, restaurant = item
                    subtotal = price * quantity
                    delivery_fee = 2.00
                    total = subtotal + delivery_fee
                    
                    c.execute("""
                        INSERT INTO orders (user_id, total_amount, delivery_fee, status)
                        VALUES (?, ?, ?, ?)
                    """, (user[0], total, delivery_fee, 'pending'))
                    
                    order_id = c.lastrowid
                    
                    # Add order item
                    c.execute("""
                        INSERT INTO order_items (order_id, menu_item_id, quantity, item_price, special_instructions)
                        VALUES (?, ?, ?, ?, ?)
                    """, (order_id, item_id, price, quantity, special_request))
                    
                    conn.commit()
                    
                    # Get next delivery time
                    from datetime import datetime, timedelta
                    now = datetime.now()
                    next_hour = (now.replace(microsecond=0, second=0, minute=0) + timedelta(hours=1))
                    delivery_time = next_hour.strftime("%I:%M %p")
                    
                    html_response += f"<p><strong>Thank you for your TreeHouse order!</strong></p>"
                    html_response += f"<p><strong>ORDER #{order_id}</strong></p>"
                    html_response += f"<p>Restaurant: {restaurant}</p>"
                    html_response += f"<p>{quantity}x {item_name} - ${subtotal:.2f}</p>"
                    if special_request:
                        html_response += f"<p>Special request: {special_request}</p>"
                    html_response += f"<p>Delivery fee: ${delivery_fee:.2f}</p>"
                    html_response += f"<p>Total: ${total:.2f}</p>"
                    html_response += f"<p>Your order will be ready for pickup at {delivery_time} from your dorm host.</p>"
                    html_response += f"<p>You can pay when you receive your order.</p>"
                else:
                    html_response += f"<p>Item #{item_id} not found</p>"
        except Exception as e:
            html_response += f"<p>Error processing order: {str(e)}</p>"
    
    else:
        html_response += "<p>Unknown command. Try 'menu', a number, or 'order X,Y,Z'</p>"
    
    conn.close()
    
    # Form for testing
    return f"""
    <html>
        <head>
            <title>SMS Test</title>
            <style>
                body {{ font-family: Arial, sans-serif; padding: 20px; max-width: 800px; margin: 0 auto; }}
                form {{ background: #f5f5f5; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
                .response {{ background: #e9f5e9; padding: 20px; border-radius: 8px; }}
                input, button {{ padding: 8px; margin-bottom: 10px; }}
                h1, h2, h3, h4 {{ color: #1B4332; }}
                code {{ background: #eee; padding: 3px 5px; border-radius: 3px; }}
                .examples {{ margin-top: 30px; background: #f8f8f8; padding: 15px; border-radius: 8px; }}
            </style>
        </head>
        <body>
            <h1>TreeHouse SMS Simulator</h1>
            
            <form>
                <div>
                    <label for="phone">Phone Number:</label>
                    <input type="text" id="phone" name="phone" value="{test_phone}" style="width: 150px;">
                </div>
                <div>
                    <label for="message">Message:</label>
                    <input type="text" id="message" name="message" value="{test_message}" style="width: 300px;">
                </div>
                <button type="submit">Send</button>
            </form>
            
            <div class="response">
                {html_response}
            </div>
            
            <div class="examples">
                <h3>Example Commands:</h3>
                <ul>
                    <li><code>menu</code> - Get the list of restaurants</li>
                    <li><code>1</code> or <code>2</code> or <code>3</code> - View the menu for that restaurant</li>
                    <li><code>order 1,2,extra sauce</code> - Order item #1, quantity 2, with special request</li>
                </ul>
            </div>
        </body>
    </html>
    """

if __name__ == '__main__':
    app.run(debug=True, port=5001)
