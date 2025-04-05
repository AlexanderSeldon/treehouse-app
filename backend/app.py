import os
from twilio.rest import Client
from dotenv import load_dotenv
import logging
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3
from twilio.twiml.messaging_response import MessagingResponse
import stripe


# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

active_sessions = {}  # Store active ordering sessions by phone number

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

# Stripe setup
stripe_secret_key = os.getenv('STRIPE_SECRET_KEY')
if stripe_secret_key:
    stripe.api_key = stripe_secret_key
    logger.info("Stripe client initialized successfully")
else:
    logger.warning("Stripe credentials not found")

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
                    body=f"New TreeHouse signup! Phone: {phone_number}, Dorm/Building: {dorm_building or 'Not specified'}",
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

# At the top of your file, add this to store active ordering sessions


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
        # Auto-register the user if they're not in the system
        c.execute("INSERT INTO users (phone_number) VALUES (?)", (clean_phone,))
        conn.commit()
        c.execute("SELECT id FROM users WHERE phone_number = ?", (clean_phone,))
        user = c.fetchone()
        welcome_msg = "Welcome to TreeHouse! You've been automatically registered. "
    else:
        welcome_msg = ""
    
    user_id = user[0]
    
    # Create a TwiML response
    resp = MessagingResponse()
    
    # Process command
    if incoming_message == 'menu' or incoming_message == 'restaurants':
        # Get restaurant data from the frontend links
        restaurants = [
            {"name": "Chick-fil-A", "link": "https://order.chick-fil-a.com/menu"},
            {"name": "Panda Express", "link": "https://www.pandaexpress.com/location/roosevelt-canal-px/menu"},
            {"name": "Subway", "link": "https://restaurants.subway.com/united-states/il/chicago/750-s-halsted-st"},
            {"name": "Jim's Original", "link": "http://www.jimsoriginal.com/"},
            {"name": "Al's Beef", "link": "https://www.alsbeef.com/chicago-little-italy-taylor-street"},
            {"name": "Busy Burger", "link": "https://www.busyburger.com/menus"},
            {"name": "Portillo's", "link": "https://order.portillos.com/menu/portillos-hot-dogs-chicago/"},
            {"name": "Chipotle", "link": "https://locations.chipotle.com/il/chicago/1132-s-clinton-st"},
            {"name": "Dunkin", "link": "https://locations.dunkindonuts.com/en/il/chicago/750-s-halsted-st-university/349361"},
            {"name": "Au Bon Pain", "link": "https://www.aubonpain.com/menu"},
            {"name": "Thai Bowl", "link": "http://places.singleplatform.com/thai-bowl-2/menu"},
            {"name": "Mario's Italian Ice", "link": "http://www.marioslemonade.com/menu"},
            {"name": "Gather Tea Bar", "link": "http://www.gathersteabar.com/"},
            {"name": "Lulu's Hot Dogs", "link": "http://lulushotdogs.com/"}
        ]
        
        response = welcome_msg + "TreeHouse Restaurant Options:\n\n"
        for idx, restaurant in enumerate(restaurants, 1):
            response += f"{idx}. {restaurant['name']} - {restaurant['link']}\n"
        
        response += "\nTo order, text 'ORDER' followed by what you want from any restaurant. "
        response += "Don't see a restaurant you want? Call (708) 901-1754 to order.\n\n"
        response += "When you're ready to pay, text 'PAY' to get a payment link."
        
        resp.message(response)
        logger.info(f"Sent restaurant list to {from_number} using TwiML")
    
    elif incoming_message.startswith('order ') or incoming_message == 'order':
        # Process order with free-form text
        if incoming_message == 'order':
            response = "Please tell us what you'd like to order by texting 'ORDER' followed by your items. For example: 'ORDER 2 burritos from Chipotle with guac and chips'"
        else:
            # Extract order text (everything after "order ")
            order_text = incoming_message[6:].strip()
            
            # Save the order in the session
            if clean_phone not in active_sessions:
                import datetime as dt
                active_sessions[clean_phone] = {
                    'user_id': user_id,
                    'order_text': order_text,
                    'started_at': dt.datetime.now()
                }
            else:
                active_sessions[clean_phone]['order_text'] = order_text
            
            # Acknowledge the order
            response = f"Got it! Your order: {order_text}\n\n"
            response += "Text 'PAY' to receive a payment link. You'll enter the exact amount of your order plus our $2-4 delivery fee."
        
        resp.message(response)
        logger.info(f"Processed order request from {from_number} using TwiML")
    
    elif incoming_message == 'pay':
        # Check if they have an active order
        has_active_order = clean_phone in active_sessions
        
        # Default delivery fee (always $3)
        delivery_fee = 3.00
        
        if stripe_secret_key:
            # Use Stripe for payment processing
            try:
                # Create a Stripe Checkout Session with automatic $3 delivery fee
                checkout_session = stripe.checkout.Session.create(
                    payment_method_types=['card'],
                    line_items=[
                        {
                            'price_data': {
                                'currency': 'usd',
                                'product_data': {
                                    'name': 'TreeHouse Delivery Fee',
                                },
                                'unit_amount': int(delivery_fee * 100),  # Convert to cents
                            },
                            'quantity': 1,
                        },
                        {
                            'price_data': {
                                'currency': 'usd',
                                'product': 'prod_S4AmnpLNObMYOs',  # Your product ID
                                'unit_amount': 1000,  # Set a default amount of $10.00 (1000 cents)
                                'unit_amount_decimal': "1000",  # Same as unit_amount but as a string
                            },
                            'quantity': 1,
                        },
                    ],
                    mode='payment',
                    success_url=f'https://treehouseneighbor.com/payment-success?session_id={{CHECKOUT_SESSION_ID}}',
                    cancel_url='https://treehouseneighbor.com/payment-cancel',
                    metadata={
                        'phone_number': clean_phone,
                        'has_active_order': str(has_active_order),
                        'user_id': str(user_id),
                    },
                )
                
                # Store the session ID in the active session
                payment_session_id = checkout_session.id
                if not has_active_order:
                    import datetime as dt
                    active_sessions[clean_phone] = {
                        'user_id': user_id,
                        'payment_session_id': payment_session_id,
                        'started_at': dt.datetime.now()
                    }
                else:
                    active_sessions[clean_phone]['payment_session_id'] = payment_session_id
                
                # Create the payment link
                payment_link = checkout_session.url
                
                # Send payment instructions
                response = "Here's your payment link:\n" + payment_link + "\n\n"
                response += "The $3 delivery fee is automatically included. Please enter the exact price of your food order only."
                
                if has_active_order:
                    order_text = active_sessions[clean_phone].get('order_text', '')
                    response += f"\n\nFor reference, your order was: {order_text}"
                
                resp.message(response)
                logger.info(f"Sent Stripe payment link to {from_number} using TwiML")
                
                # Send notification to admin
                if client:
                    try:
                        admin_note = f"PAYMENT REQUESTED!\n\n"
                        admin_note += f"Customer: {from_number}\n"
                        if has_active_order:
                            admin_note += f"Order: {active_sessions[clean_phone].get('order_text', 'No order text')}\n"
                        else:
                            admin_note += "Note: Customer likely called in their order\n"
                        admin_note += f"Stripe Session ID: {payment_session_id}"
                        
                        client.messages.create(
                            body=admin_note,
                            from_=twilio_phone,
                            to=notification_email
                        )
                    except Exception as e:
                        logger.error(f"Error sending admin notification: {e}")
                        
            except Exception as e:
                logger.error(f"Error creating Stripe session: {e}")
                response = "Sorry, there was an error generating your payment link. Please try again or call (708) 901-1754 for assistance."
                resp.message(response)
        else:
            # Fallback to the placeholder payment link if Stripe is not configured
            import datetime as dt
            payment_session_id = f"pay_{clean_phone}_{int(dt.datetime.now().timestamp())}"
            
            # Prepare a fake payment link as fallback
            payment_link = f"https://treehouseneighbor.com/pay/{payment_session_id}"
            
            # Save the payment session
            if not has_active_order:
                active_sessions[clean_phone] = {
                    'user_id': user_id,
                    'payment_session_id': payment_session_id,
                    'started_at': dt.datetime.now()
                }
            else:
                active_sessions[clean_phone]['payment_session_id'] = payment_session_id
            
            # Send payment instructions
            response = "Here's your payment link:\n" + payment_link + "\n\n"
            response += "Please enter the exact price of your order from the restaurant menu. The $3 delivery fee is automatically added."
            
            if has_active_order:
                order_text = active_sessions[clean_phone].get('order_text', '')
                response += f"\n\nFor reference, your order was: {order_text}"
            
            resp.message(response)
            logger.info(f"Sent placeholder payment link to {from_number} using TwiML (Stripe not configured)")
            
            # Send notification to admin
            if client:
                try:
                    admin_note = f"PAYMENT REQUESTED!\n\n"
                    admin_note += f"Customer: {from_number}\n"
                    if has_active_order:
                        admin_note += f"Order: {active_sessions[clean_phone].get('order_text', 'No order text')}\n"
                    else:
                        admin_note += "Note: Customer likely called in their order\n"
                    
                    client.messages.create(
                        body=admin_note,
                        from_=twilio_phone,
                        to=notification_email
                    )
                except Exception as e:
                    logger.error(f"Error sending admin notification: {e}")
    
    elif incoming_message in ['help', 'info']:
        # Provide help information
        response = "TreeHouse - Restaurant delivery for ONLY $2-4!\n\n"
        response += "Commands:\n"
        response += "• Text 'MENU' to see available restaurants\n"
        response += "• Text 'ORDER' followed by what you want (e.g., 'ORDER 2 burritos from Chipotle')\n"
        response += "• Text 'PAY' to get a payment link\n"
        response += "• Call (708) 901-1754 for special orders or questions\n\n"
        response += "Food is delivered hourly. Order by :25-:30 of each hour to get your food at the top of the next hour."
        
        resp.message(response)
        logger.info(f"Sent help info to {from_number} using TwiML")
    
    else:
        # Handle unknown commands
        response = "I didn't understand that command. Text 'MENU' to see restaurants, 'ORDER' followed by what you want, or 'PAY' to get a payment link. Need help? Text 'HELP' or call (708) 901-1754."
        
        resp.message(response)
        logger.info(f"Sent unknown command response to {from_number} using TwiML")
    
    conn.close()
    return str(resp)

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
    
    # Check if user exists, create if not
    c.execute("SELECT id FROM users WHERE phone_number = ?", (clean_phone,))
    user = c.fetchone()
    
    if not user:
        # Add test user if not found
        c.execute("INSERT INTO users (phone_number) VALUES (?)", (clean_phone,))
        conn.commit()
        c.execute("SELECT id FROM users WHERE phone_number = ?", (clean_phone,))
        user = c.fetchone()
        html_response += f"<p>Created new test user with phone: {test_phone}</p>"
    
    user_id = user[0]
    
    # Handle the message based on content
    if test_message.lower() in ['menu', 'restaurants']:
        # Display restaurant list with links
        restaurants = [
            {"name": "Chick-fil-A", "link": "https://order.chick-fil-a.com/menu"},
            {"name": "Panda Express", "link": "https://www.pandaexpress.com/location/roosevelt-canal-px/menu"},
            {"name": "Subway", "link": "https://restaurants.subway.com/united-states/il/chicago/750-s-halsted-st"},
            {"name": "Jim's Original", "link": "http://www.jimsoriginal.com/"},
            {"name": "Al's Beef", "link": "https://www.alsbeef.com/chicago-little-italy-taylor-street"},
            {"name": "Busy Burger", "link": "https://www.busyburger.com/menus"},
            {"name": "Portillo's", "link": "https://order.portillos.com/menu/portillos-hot-dogs-chicago/"},
            {"name": "Chipotle", "link": "https://locations.chipotle.com/il/chicago/1132-s-clinton-st"},
            {"name": "Dunkin", "link": "https://locations.dunkindonuts.com/en/il/chicago/750-s-halsted-st-university/349361"},
            {"name": "Au Bon Pain", "link": "https://www.aubonpain.com/menu"},
            {"name": "Thai Bowl", "link": "http://places.singleplatform.com/thai-bowl-2/menu"},
            {"name": "Mario's Italian Ice", "link": "http://www.marioslemonade.com/menu"},
            {"name": "Gather Tea Bar", "link": "http://www.gathersteabar.com/"},
            {"name": "Lulu's Hot Dogs", "link": "http://lulushotdogs.com/"}
        ]
        
        html_response += "<p><strong>Available Restaurants:</strong></p><ol>"
        for restaurant in restaurants:
            html_response += f"<li><a href='{restaurant['link']}' target='_blank'>{restaurant['name']}</a></li>"
        html_response += "</ol>"
        html_response += "<p>To order, text 'ORDER' followed by what you want. Don't see a restaurant you want? Call (708) 901-1754 to order.</p>"
        html_response += "<p>Text 'PAY' when you're ready to pay.</p>"
    
    elif test_message.lower().startswith('order '):
        # Process a free-form order
        order_text = test_message[6:].strip()
        
        # Store in active session
        import datetime as dt
        if clean_phone not in active_sessions:
            active_sessions[clean_phone] = {
                'user_id': user_id,
                'order_text': order_text,
                'started_at': dt.datetime.now()
            }
        else:
            active_sessions[clean_phone]['order_text'] = order_text
        
        html_response += f"<p><strong>Order Received:</strong> {order_text}</p>"
        html_response += "<p>Text 'PAY' to get a payment link.</p>"
    
    elif test_message.lower() == 'order':
        html_response += "<p>Please tell us what you'd like to order by texting 'ORDER' followed by your items.</p>"
        html_response += "<p>For example: 'ORDER 2 burritos from Chipotle with guac and chips'</p>"
    
    elif test_message.lower() == 'pay':
        # Generate a payment link - either real Stripe or simulation
        import datetime as dt
        payment_session_id = f"pay_{clean_phone}_{int(dt.datetime.now().timestamp())}"
        payment_link = ""
        
        # If Stripe is configured, create a real checkout session for testing
        if stripe_secret_key:
            try:
                # Create an actual Stripe checkout session
                checkout_session = stripe.checkout.Session.create(
                    payment_method_types=['card'],
                    line_items=[
                        {
                            'price_data': {
                                'currency': 'usd',
                                'product_data': {
                                    'name': 'TreeHouse Delivery Fee',
                                },
                                'unit_amount': 300,  # $3.00
                            },
                            'quantity': 1,
                        },
                        {
                            'price_data': {
                                'currency': 'usd',
                                'product': 'price_1RAFIgAKf1IOilM7UwJ9qO6y',  # Your product ID
                                'unit_amount': 1000,  # Default $10.00 (1000 cents)
                                'unit_amount_decimal': "1000",  # Same as unit_amount but as a string
                            },
                            'quantity': 1,
                        },
                    ],
                    mode='payment',
                    success_url=request.base_url + '?result=success&session_id={CHECKOUT_SESSION_ID}',
                    cancel_url=request.base_url + '?result=cancel',
                    metadata={
                        'phone_number': clean_phone,
                        'test': 'true',
                        'user_id': str(user_id),
                    },
                )
                
                payment_session_id = checkout_session.id
                payment_link = checkout_session.url
                html_response += "<p><strong>Real Stripe Checkout Created!</strong></p>"
                
            except Exception as e:
                logger.error(f"Error creating test Stripe session: {e}")
                payment_link = f"https://checkout.stripe.com/pay/test_{payment_session_id}"
                html_response += f"<p><strong>Error creating Stripe session:</strong> {str(e)}</p>"
                html_response += "<p>Using simulation instead.</p>"
        else:
            # Use a simulation
            payment_link = f"https://checkout.stripe.com/pay/test_{payment_session_id}"
            html_response += "<p>Stripe not configured. Using simulation.</p>"
        
        # Store or update in active session
        if clean_phone not in active_sessions:
            active_sessions[clean_phone] = {
                'user_id': user_id,
                'payment_session_id': payment_session_id,
                'started_at': dt.datetime.now()
            }
            html_response += "<p>No active order found, but still generating payment link.</p>"
        else:
            active_sessions[clean_phone]['payment_session_id'] = payment_session_id
            order_text = active_sessions[clean_phone].get('order_text')
            if order_text:
                html_response += f"<p><strong>Your order:</strong> {order_text}</p>"
        
        html_response += f"<p><strong>Payment Link:</strong> <a href='{payment_link}' target='_blank'>{payment_link}</a></p>"
        html_response += "<p>The $3 delivery fee is automatically included. Please enter the exact price of your food order only.</p>"
        
        # If Stripe is not configured, show a visual simulation
        if not stripe_secret_key:
            html_response += """
            <div id="stripeSimulator" style="margin-top:20px; padding:20px; border:1px solid #ccc; border-radius:8px; background-color:#f8f9fa;">
                <h3 style="margin-top:0;">Stripe Checkout Simulation</h3>
                <div style="background-color:#fff; border:1px solid #eee; border-radius:4px; padding:15px; margin-bottom:15px;">
                    <div style="margin-bottom:10px; font-weight:bold;">TreeHouse Food Delivery</div>
                    <div style="display:flex; justify-content:space-between; margin-bottom:8px;">
                        <div>Delivery Fee</div>
                        <div>$3.00</div>
                    </div>
                    <div style="display:flex; justify-content:space-between; margin-bottom:15px;">
                        <div>Food Order</div>
                        <div><input type="number" id="orderAmount" min="1" step="0.01" value="15.00" style="width:70px; text-align:right;"></div>
                    </div>
                    <div style="display:flex; justify-content:space-between; padding-top:10px; border-top:1px solid #eee; font-weight:bold;">
                        <div>Total</div>
                        <div id="totalAmount">$18.00</div>
                    </div>
                </div>
                <button onclick="simulatePayment()" style="background-color:#5469d4; color:white; border:none; padding:10px 15px; border-radius:4px; cursor:pointer;">Pay</button>
            </div>
            
            <script>
            function updateTotal() {
                const orderAmount = parseFloat(document.getElementById('orderAmount').value) || 0;
                const total = (orderAmount + 3).toFixed(2);
                document.getElementById('totalAmount').innerText = '$' + total;
            }
            
            document.getElementById('orderAmount').addEventListener('input', updateTotal);
            
            function simulatePayment() {
                const total = parseFloat(document.getElementById('orderAmount').value) + 3;
                alert('Payment simulation: $' + total.toFixed(2) + ' would be charged to your card.\\n\\nIn the real system, this would trigger a webhook that notifies both you and the TreeHouse team about your successful payment.');
                window.location.href = window.location.href + '?result=success&simulation=true';
            }
            </script>
            """
        
        # Simulate admin notification
        html_response += "<div style='margin-top: 20px; padding: 10px; background-color: #f8f9fa; border: 1px solid #ddd;'>"
        html_response += "<p><strong>Admin Notification:</strong></p>"
        html_response += f"<p>PAYMENT REQUESTED!<br/>Customer: {test_phone}</p>"
        
        if clean_phone in active_sessions and 'order_text' in active_sessions[clean_phone]:
            html_response += f"<p>Order: {active_sessions[clean_phone]['order_text']}</p>"
        else:
            html_response += "<p>Note: Customer likely called in their order</p>"
        
        html_response += f"<p>Session ID: {payment_session_id}</p>"
        html_response += "</div>"
    
    # Handle success/cancel redirects
    result = request.args.get('result')
    if result == 'success':
        simulation = request.args.get('simulation', 'false')
        session_id = request.args.get('session_id', payment_session_id if 'payment_session_id' in locals() else '')
        
        success_html = f"""
        <div style="margin-top: 20px; padding: 20px; background-color: #d4edda; border-radius: 8px; text-align: center;">
            <h3 style="color: #155724; margin-top:0;">Payment Successful!</h3>
            <p>Your order has been processed. You would receive a text confirmation shortly.</p>
            <p>Session ID: {session_id}</p>
            <p>{'(Simulated payment)' if simulation == 'true' else ''}</p>
        </div>
        """
        html_response += success_html
    elif result == 'cancel':
        cancel_html = """
        <div style="margin-top: 20px; padding: 20px; background-color: #f8d7da; border-radius: 8px; text-align: center;">
            <h3 style="color: #721c24; margin-top:0;">Payment Cancelled</h3>
            <p>Your payment was cancelled. You would need to text PAY again to get a new payment link.</p>
        </div>
        """
        html_response += cancel_html
    
    elif test_message.lower() in ['help', 'info']:
        html_response += "<p><strong>TreeHouse Help</strong></p>"
        html_response += "<ul>"
        html_response += "<li>Text 'MENU' to see available restaurants</li>"
        html_response += "<li>Text 'ORDER' followed by what you want</li>"
        html_response += "<li>Text 'PAY' to get a payment link</li>"
        html_response += "<li>Call (708) 901-1754 for special orders or questions</li>"
        html_response += "</ul>"
        html_response += "<p>Food is delivered hourly. Order by :25-:30 of each hour to get your food at the top of the next hour.</p>"
    
    else:
        html_response += "<p>I didn't understand that command. Text 'MENU' to see restaurants, 'ORDER' followed by what you want, or 'PAY' to get a payment link.</p>"
        html_response += "<p>Need help? Text 'HELP' or call (708) 901-1754.</p>"
    
    conn.close()
    
    # Display active session if it exists
    if clean_phone in active_sessions:
        session_info = active_sessions[clean_phone]
        html_response += "<div style='margin-top: 20px; padding: 10px; background-color: #e9f7ef; border: 1px solid #ddd;'>"
        html_response += "<p><strong>Current Session Info:</strong></p>"
        
        for key, value in session_info.items():
            if key != 'started_at':  # Skip the timestamp for clarity
                html_response += f"<p>{key}: {value}</p>"
                
        html_response += "</div>"
    
    # Form for testing
    return f"""
    <html>
        <head>
            <title>TreeHouse SMS Test</title>
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
                    <li><code>menu</code> or <code>restaurants</code> - See available restaurants</li>
                    <li><code>order</code> - Get ordering instructions</li>
                    <li><code>order 2 burritos from Chipotle with extra guac</code> - Place a free-form order</li>
                    <li><code>pay</code> - Get a payment link</li>
                    <li><code>help</code> or <code>info</code> - Get help information</li>
                </ul>
            </div>
        </body>
    </html>
    """



@app.route('/payment-success')
def payment_success():
    session_id = request.args.get('session_id')
    return f"""
    <html>
        <head>
            <title>Payment Successful</title>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{ font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; }}
                .success {{ background: #e9f7ef; padding: 20px; border-radius: 8px; text-align: center; }}
                h1 {{ color: #1B4332; }}
            </style>
        </head>
        <body>
            <div class="success">
                <h1>Payment Successful!</h1>
                <p>Your order has been processed. You will receive a text confirmation shortly.</p>
                <p>Thank you for ordering with TreeHouse!</p>
                <p><a href="https://treehouseneighbor.com">Return to TreeHouse</a></p>
            </div>
        </body>
    </html>
    """

@app.route('/payment-cancel')
def payment_cancel():
    return f"""
    <html>
        <head>
            <title>Payment Cancelled</title>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{ font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; }}
                .cancel {{ background: #f8d7da; padding: 20px; border-radius: 8px; text-align: center; }}
                h1 {{ color: #721c24; }}
            </style>
        </head>
        <body>
            <div class="cancel">
                <h1>Payment Cancelled</h1>
                <p>Your payment was cancelled. If you still want to place an order, please text PAY again.</p>
                <p>If you need assistance, call (708) 901-1754.</p>
                <p><a href="https://treehouseneighbor.com">Return to TreeHouse</a></p>
            </div>
        </body>
    </html>
    """

@app.route('/webhook/stripe', methods=['POST'])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    endpoint_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
    
    event = None
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError as e:
        # Invalid payload
        logger.error(f"Invalid Stripe payload: {e}")
        return jsonify({"error": "Invalid payload"}), 400
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        logger.error(f"Invalid Stripe signature: {e}")
        return jsonify({"error": "Invalid signature"}), 400
    
    # Handle the checkout.session.completed event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        
        # Extract metadata
        phone_number = session.get('metadata', {}).get('phone_number')
        user_id = session.get('metadata', {}).get('user_id')
        
        if phone_number and user_id:
            # Get payment details
            payment_amount = session.get('amount_total', 0) / 100  # Convert cents to dollars
            payment_id = session.get('id')
            
            # Record payment in database
            try:
                conn = sqlite3.connect('treehouse.db')
                c = conn.cursor()
                
                # Create a record in your payments table
                c.execute(
                    "INSERT INTO payments (order_id, amount, payment_method, transaction_id, status) VALUES (?, ?, ?, ?, ?)",
                    (0, payment_amount, "stripe", payment_id, "completed")
                )
                
                conn.commit()
                conn.close()
                logger.info(f"Payment recorded for user_id {user_id}, amount ${payment_amount}")
                
                # Notify the user about successful payment
                if client:
                    try:
                        message = client.messages.create(
                            body=f"Payment received! Amount: ${payment_amount:.2f}. Your order will be delivered soon.",
                            from_=twilio_phone,
                            to=f"+{phone_number}"
                        )
                        logger.info(f"Payment confirmation sent to +{phone_number}")
                    except Exception as e:
                        logger.error(f"Error sending payment confirmation: {e}")
                
                # Notify admin about payment
                if client:
                    try:
                        client.messages.create(
                            body=f"Payment received! Phone: +{phone_number}, Amount: ${payment_amount:.2f}, Stripe ID: {payment_id}",
                            from_=twilio_phone,
                            to=notification_email
                        )
                        logger.info(f"Admin payment notification sent")
                    except Exception as e:
                        logger.error(f"Error sending admin payment notification: {e}")
                
            except Exception as e:
                logger.error(f"Error recording payment: {e}")
    
    return jsonify({"status": "success"}), 200


@app.route('/')
def serve_react_app():
    return send_from_directory('static/react', 'index.html')

@app.route('/static/css/<path:filename>')
def serve_css(filename):
    return send_from_directory('static/react/static/css', filename)

@app.route('/static/js/<path:filename>')
def serve_js(filename):
    return send_from_directory('static/react/static/js', filename)

@app.route('/static/media/<path:filename>')
def serve_media(filename):
    return send_from_directory('static/react/static/media', filename)

@app.route('/static/<path:path>')
def serve_static(path):
    return send_from_directory('static/react', path)


@app.route('/debug-files')
def debug_files():
    import os
    result = {
        'cwd': os.getcwd(),
        'files': {}
    }
    
    # Check existence of directories
    paths = [
        '.',
        'static',
        'static/react', 
        'static/react/static', 
        'static/react/static/js',
        'static/react/static/css'
    ]
    
    for path in paths:
        if os.path.exists(path):
            result['files'][path] = os.listdir(path)
        else:
            result['files'][path] = f"Directory does not exist: {path}"
    
    return jsonify(result)

@app.route('/debug-html')
def debug_html():
    import os
    try:
        with open('static/react/index.html', 'r') as f:
            html_content = f.read()
        return html_content
    except Exception as e:
        return str(e)

@app.route('/debug-test')
def debug_test():
    return "This is a test endpoint"

@app.route('/<path:path>')
def serve_react_files(path):
    if path.startswith('api/'):
        # This will be handled by your existing API routes
        return {"error": "API endpoint not found"}, 404
    try:
        return send_from_directory('static/react', path)
    except Exception:
        return send_from_directory('static/react', 'index.html')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=True)
