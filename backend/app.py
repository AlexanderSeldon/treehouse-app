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
import openai
import random
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

try:
    from uber_direct_delivery import UberDirectDelivery, prepare_batch_for_delivery
    UBER_DIRECT_AVAILABLE = True
except ImportError:
    UBER_DIRECT_AVAILABLE = False
    logging.warning("Uber Direct module not available. Delivery functionality will be limited.")

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
    
    # Batch tracking table
    c.execute('''
        CREATE TABLE IF NOT EXISTS batch_tracking (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            restaurant_name TEXT NOT NULL,
            batch_time TIMESTAMP NOT NULL,
            current_orders INTEGER DEFAULT 0,
            max_orders INTEGER DEFAULT 10,
            location TEXT,
            delivery_fee DECIMAL(5,2) DEFAULT 4.00,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

# Add this function to update the database schema for consent tracking
def update_database_schema():
    """Add SMS consent tracking fields to the database"""
    conn = sqlite3.connect('treehouse.db')
    c = conn.cursor()
    
    # Check if users table has the consent columns
    c.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in c.fetchall()]
    
    # Add sms_consent column if it doesn't exist
    if 'sms_consent' not in columns:
        c.execute("ALTER TABLE users ADD COLUMN sms_consent BOOLEAN DEFAULT 0")
        logger.info("Added sms_consent column to users table")
    
    # Add opt_in_timestamp column if it doesn't exist
    if 'opt_in_timestamp' not in columns:
        c.execute("ALTER TABLE users ADD COLUMN opt_in_timestamp TIMESTAMP")
        logger.info("Added opt_in_timestamp column to users table")
    
    conn.commit()
    conn.close()
    logger.info("Database schema updated for consent tracking")

# Initialize the database when the app starts
init_db()
update_database_schema()

# Twilio setup
account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')
twilio_phone = os.getenv('TWILIO_PHONE_NUMBER')
notification_email = os.getenv('NOTIFICATION_EMAIL')

# Twilio setup
twilio_client = None  # Rename this
if account_sid and auth_token:
    try:
        twilio_client = Client(account_sid, auth_token)  # Use twilio_client
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

stripe.api_version = "2025-03-31.basil"

# OpenAI setup
openai_api_key = os.getenv('OPENAI_API_KEY')
if openai_api_key:
    openai_client = openai.OpenAI(api_key=openai_api_key)  # Use openai_client
    logger.info("OpenAI client initialized successfully")
else:
    logger.warning("OpenAI API key not found")


# Hot restaurants rotator - from HotSpotSection.js
# This will rotate through popular restaurants for each batch
hot_restaurants = [
    {"name": "Chipotle", "fee": 4.00, "orders": 5, "freeItem": "Free chips & guac"},
    {"name": "McDonald's", "fee": 4.00, "orders": 6, "freeItem": "Free medium fries"},
    {"name": "Chick-fil-A", "fee": 4.00, "orders": 5, "freeItem": "Free cookie"},
    {"name": "Portillo's", "fee": 4.00, "orders": 5, "freeItem": "Free cheese fries"},
    {"name": "Starbucks", "fee": 4.00, "orders": 6, "freeItem": "Free cookie"}
]

other_restaurants = [
    {"name": "Raising Cane's", "fee": 7.99, "freeItem": "Free Texas toast"},
    {"name": "Subway", "fee": 8.99, "freeItem": "Free cookie"},
    {"name": "Panda Express", "fee": 7.49, "freeItem": "Free eggroll"},
    {"name": "Five Guys", "fee": 9.99, "freeItem": "Free small fries"}
]

def init_restaurant_batches():
    now = datetime.now()
    current_hour = now.hour
    current_minute = now.minute
    
    # Find next batch time
    # If between XX:00-XX:15, next batch is XX:30
    # If between XX:15-XX:30, current batch is XX:30
    # If between XX:30-XX:45, next batch is (XX+1):00
    # If between XX:45-XX:00, current batch is (XX+1):00
    if 0 <= current_minute < 15:
        next_batch_hour = current_hour
        next_batch_minute = 30
    elif 15 <= current_minute < 30:
        next_batch_hour = current_hour
        next_batch_minute = 30
    elif 30 <= current_minute < 45:
        next_batch_hour = current_hour + 1
        next_batch_minute = 0
    else:  # 45 <= current_minute < 60
        next_batch_hour = current_hour + 1
        next_batch_minute = 0
    
    if next_batch_hour >= 24:
        next_batch_hour = 0
    
    next_batch_time = datetime(now.year, now.month, now.day, next_batch_hour, next_batch_minute)
    
    # Check if we're past midnight and need to adjust to next day
    if next_batch_hour < current_hour:
        next_day = now + timedelta(days=1)
        next_batch_time = datetime(next_day.year, next_day.month, next_day.day, next_batch_hour, next_batch_minute)
    
    conn = sqlite3.connect('treehouse.db')
    c = conn.cursor()
    
    # Clear previous batches that haven't happened yet
    c.execute("DELETE FROM batch_tracking WHERE batch_time > ?", (now,))
    
    # Create batches for the next few hours
    locations = ["Student Center", "James Stukel Tower", "University Hall", "Library"]
    
    for i in range(3):  # Create 3 upcoming batches
        batch_time = next_batch_time + timedelta(minutes=30*i)
        
        # For each restaurant, create a batch
        for restaurant in hot_restaurants:
            location = random.choice(locations)
            c.execute(
                """INSERT INTO batch_tracking 
                   (restaurant_name, batch_time, current_orders, max_orders, location, delivery_fee)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (restaurant["name"], batch_time, restaurant["orders"], 10, location, restaurant["fee"])
            )
    
    conn.commit()
    conn.close()

# Initialize batches at startup
init_restaurant_batches()

@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.json
    phone_number = data.get('phone_number')
    name = data.get('name')
    email = data.get('email')
    dorm_building = data.get('dorm_building')
    room_number = data.get('room_number')
    
    # New consent fields
    sms_consent = data.get('sms_consent', False)
    opt_in_timestamp = data.get('opt_in_timestamp', datetime.now().isoformat())
    
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
            user_id = user[0]
            query_parts = []
            params = []
            
            if name:
                query_parts.append("name = ?")
                params.append(name)
            if email:
                query_parts.append("email = ?")
                params.append(email)
            if dorm_building:
                query_parts.append("dorm_building = ?")
                params.append(dorm_building)
            if room_number:
                query_parts.append("room_number = ?")
                params.append(room_number)
            
            # Always update consent information
            query_parts.append("sms_consent = ?")
            params.append(sms_consent)
            
            query_parts.append("opt_in_timestamp = ?")
            params.append(opt_in_timestamp)
            
            # Create the update query
            if query_parts:
                query = "UPDATE users SET " + ", ".join(query_parts) + " WHERE id = ?"
                params.append(user_id)
                c.execute(query, params)
            
            is_new_user = False
        else:
            # Insert new user
            c.execute(
                """INSERT INTO users 
                   (phone_number, name, email, dorm_building, room_number, sms_consent, opt_in_timestamp) 
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (clean_phone, name, email, dorm_building, room_number, sms_consent, opt_in_timestamp)
            )
            user_id = c.lastrowid
            is_new_user = True
        
        conn.commit()
        conn.close()
        
        # Send notification via Twilio if it's a new user and they consented
        if is_new_user and sms_consent and twilio_client:
            try:
                # Send welcome message to the new user
                welcome_message = (
                    f"Welcome to TreeHouse! You're all set to receive our notifications. "
                    f"Text MENU to see restaurant options, ORDER to place an order, or HELP for assistance. "
                    f"Reply STOP at any time to unsubscribe. Msg & data rates may apply."
                )
                
                message = twilio_client.messages.create(
                    body=welcome_message,
                    from_=twilio_phone,  # Send from your Twilio number
                    to=f"+{clean_phone}"  # Send to the new user's phone number
                )
                logger.info(f"Welcome message sent: {message.sid}")

                # Notify admin via SMS (admin's phone number)
                admin_message = (
                    f"New TreeHouse signup! Phone: {phone_number}, "
                    f"Dorm/Building: {dorm_building or 'Not specified'}, "
                    f"SMS consent: {'Yes' if sms_consent else 'No'}"
                )
                
                # Send the admin notification SMS (admin's phone number is stored in notification_email)
                twilio_client.messages.create(
                    body=admin_message,
                    from_=twilio_phone,  # Use your Twilio number to send the message
                    to=f"+{notification_email}"  # Admin's phone number (in E.164 format)
                )
                logger.info(f"Admin notification sent for new signup")
                
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
        if twilio_client:
            try:
                # Get user info for notification
                c.execute("SELECT phone_number FROM users WHERE id = ?", (user_id,))
                user_result = c.fetchone()
                user_phone = user_result[0] if user_result else "Unknown"
                
                message = twilio_client.messages.create(
                    body=f"New TreeHouse order! Order ID: {order_id}, Amount: ${total_amount:.2f}, User: {user_phone}",
                    from_=twilio_phone,
                    to=notification_email
                )
                logger.info(f"Order notification sent: {message.sid}")
            except Exception as e:
                logger.error(f"Error sending order notification: {e}")
        
        # Inside your create_order function, add this before conn.close()
        # Send detailed notification to admin
        if twilio_client:
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
                twilio_client.messages.create(
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
        if twilio_client:
            try:
                # Get user info for notification
                user_id = order[2]
                c.execute("SELECT phone_number FROM users WHERE id = ?", (user_id,))
                user_result = c.fetchone()
                user_phone = user_result[0] if user_result else "Unknown"
                
                message = twilio_client.messages.create(
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

# Functions for AI-powered SMS conversations
def get_current_batches():
    """Get current restaurant batches for the next delivery window"""
    try:
        now = datetime.now()
        conn = sqlite3.connect('treehouse.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # Get the next batch time
        c.execute("""
            SELECT * FROM batch_tracking 
            WHERE batch_time > ? 
            ORDER BY batch_time ASC 
            LIMIT 1
        """, (now,))
        next_batch = c.fetchone()
        
        if not next_batch:
            # No scheduled batches, initialize new ones
            init_restaurant_batches()
            
            # Try again
            c.execute("""
                SELECT * FROM batch_tracking 
                WHERE batch_time > ? 
                ORDER BY batch_time ASC 
                LIMIT 1
            """, (now,))
            next_batch = c.fetchone()
            
            if not next_batch:
                # Still no batches, use dynamic data
                next_batch_time = now + timedelta(minutes=30)
                
                # Adjust to correct batch time based on 15-minute windows
                current_minute = now.minute
                
                if current_minute < 15:
                    # Next batch is at XX:30
                    next_batch_time = next_batch_time.replace(minute=30, second=0, microsecond=0)
                elif current_minute < 30:
                    # Current batch is at XX:30
                    next_batch_time = next_batch_time.replace(minute=30, second=0, microsecond=0)
                elif current_minute < 45:
                    # Next batch is at (XX+1):00
                    next_batch_time = next_batch_time.replace(hour=next_batch_time.hour+1, minute=0, second=0, microsecond=0)
                else:
                    # Current batch is at (XX+1):00
                    next_batch_time = next_batch_time.replace(hour=next_batch_time.hour+1, minute=0, second=0, microsecond=0)
                
                batch_data = []
                for restaurant in hot_restaurants:
                    batch_data.append({
                        'restaurant_name': restaurant['name'],
                        'batch_time': next_batch_time,
                        'current_orders': restaurant['orders'],
                        'max_orders': 10,
                        'location': random.choice(["Student Center", "James Stukel Tower", "University Hall", "Library"]),
                        'delivery_fee': restaurant['fee'],
                        'free_item': restaurant['freeItem']
                    })
                conn.close()
                return batch_data
        
        batch_time = next_batch['batch_time']
        
        # Get all restaurants for this batch time
        c.execute("""
            SELECT * FROM batch_tracking 
            WHERE batch_time = ?
            ORDER BY restaurant_name
        """, (batch_time,))
        restaurant_batches = [dict(row) for row in c.fetchall()]
        
        # Add free item information from hot_restaurants
        for batch in restaurant_batches:
            for restaurant in hot_restaurants:
                if restaurant['name'] == batch['restaurant_name']:
                    batch['free_item'] = restaurant['freeItem']
                    break
            else:
                batch['free_item'] = "Free item"  # Default if not found
        
        conn.close()
        return restaurant_batches
    
    except Exception as e:
        logger.error(f"Error getting current batches: {e}")
        return []

def update_batch_count(restaurant_name, batch_time=None):
    """Update the order count for a specific restaurant batch"""
    try:
        conn = sqlite3.connect('treehouse.db')
        conn.row_factory = sqlite3.Row  # Add this to get row objects that can be converted to dict
        c = conn.cursor()
        
        if batch_time:
            c.execute("""
                UPDATE batch_tracking 
                SET current_orders = current_orders + 1 
                WHERE restaurant_name = ? AND batch_time = ?
            """, (restaurant_name, batch_time))
        else:
            # Get the next batch for this restaurant
            now = datetime.now()
            c.execute("""
                UPDATE batch_tracking 
                SET current_orders = current_orders + 1 
                WHERE restaurant_name = ? AND batch_time > ? 
                ORDER BY batch_time ASC 
                LIMIT 1
            """, (restaurant_name, now))
        
        conn.commit()
        
        # Get the updated batch info
        if batch_time:
            c.execute("""
                SELECT * FROM batch_tracking 
                WHERE restaurant_name = ? AND batch_time = ?
            """, (restaurant_name, batch_time))
        else:
            now = datetime.now()
            c.execute("""
                SELECT * FROM batch_tracking 
                WHERE restaurant_name = ? AND batch_time > ? 
                ORDER BY batch_time ASC 
                LIMIT 1
            """, (restaurant_name, now))
            
        batch = c.fetchone()
        conn.close()
        
        if batch:
            return dict(batch)  # Convert to a dictionary before returning
        else:
            return None
    except Exception as e:
        logger.error(f"Error updating batch count: {e}")
        return None

def extract_restaurant_from_order(order_text):
    """
    Use OpenAI to extract the restaurant from the order text
    Returns tuple of (restaurant_name, processed_order_text)
    """
    if not openai_api_key:
        # If OpenAI is not configured, use a simple keyword search
        restaurant_keywords = {
            "Chipotle": ["chipotle", "burrito", "bowl", "guac"],
            "McDonald's": ["mcdonald", "big mac", "mcnugget", "happy meal"],
            "Chick-fil-A": ["chick-fil-a", "chicken sandwich", "nuggets"],
            "Portillo's": ["portillo", "hot dog", "beef sandwich"],
            "Starbucks": ["starbuck", "coffee", "frappuccino", "latte"]
        }
        
        order_lower = order_text.lower()
        for restaurant, keywords in restaurant_keywords.items():
            if any(keyword in order_lower for keyword in keywords):
                return restaurant, order_text
        
        # If no keywords found, return None
        return None, order_text
    
    try:
        # Use OpenAI to extract restaurant and process order
        client = openai.OpenAI(api_key=openai_api_key)
        
        prompt = f"""
        Extract the restaurant name from this food order. If no specific restaurant is mentioned, 
        suggest the most likely restaurant based on the food items ordered.
        
        Only return the restaurant name, nothing else.
        
        Order text: {order_text}
        
        Available restaurants:
        - Chipotle
        - McDonald's
        - Chick-fil-A
        - Portillo's
        - Starbucks
        - Raising Cane's
        - Subway
        - Panda Express
        - Five Guys
        """
        
        response = client.completions.create(
            model="gpt-3.5-turbo-instruct",
            prompt=prompt,
            max_tokens=20,
            temperature=0.3
        )
        
        restaurant = response.choices[0].text.strip()
        
        # Handle responses that might include extra text
        for name in ["Chipotle", "McDonald's", "Chick-fil-A", "Portillo's", "Starbucks", 
                    "Raising Cane's", "Subway", "Panda Express", "Five Guys"]:
            if name in restaurant:
                return name, order_text
        
        # If no matching restaurant found, return the first available
        return "Chipotle", order_text
    
    except Exception as e:
        logger.error(f"Error using OpenAI for restaurant extraction: {e}")
        return None, order_text

def ai_generate_response(prompt, user_history=None):
   """Generate AI response using OpenAI"""
   if not openai_api_key:
       # Fallback without AI
       return "I'm sorry, I couldn't process that with AI. Please try again or text ORDER followed by what you want."
   
   try:
       client = openai.OpenAI(api_key=openai_api_key)
       
       # Get current batch information to provide to the AI
       batches = get_current_batches()
       batch_time_info = ""
       hot_restaurants_info = ""
       
       # Format batch timing information
       if batches and len(batches) > 0:
           # Get the batch time from the first batch
           batch_time = datetime.fromisoformat(str(batches[0]['batch_time'])) if isinstance(batches[0]['batch_time'], str) else batches[0]['batch_time']
           current_time = datetime.now()
           
           # Calculate when batch opens and closes
           if batch_time.minute == 30:  # It's a XX:30 batch
               batch_open_time = datetime(batch_time.year, batch_time.month, batch_time.day, batch_time.hour, 15, 0)
               batch_close_time = batch_time
               food_ready_time = batch_time + timedelta(minutes=30)  # Food ready at XX+1:00
           else:  # It's a XX:00 batch
               batch_open_time = datetime(batch_time.year, batch_time.month, batch_time.day, batch_time.hour-1 if batch_time.hour > 0 else 23, 45, 0)
               batch_close_time = batch_time
               food_ready_time = batch_time + timedelta(minutes=30)  # Food ready at XX:30
           
           # Determine if batch is currently open
           batch_is_open = batch_open_time <= current_time < batch_close_time
           
           if batch_is_open:
               # Calculate time remaining until batch closes
               time_diff = batch_close_time - current_time
               minutes_remaining = int(time_diff.total_seconds() / 60)
               seconds_remaining = int(time_diff.total_seconds() % 60)
               
               batch_time_str = batch_time.strftime("%I:%M %p")
               food_time_str = food_ready_time.strftime("%I:%M %p")
               
               urgency = ""
               if minutes_remaining < 5:
                   urgency = "🚨 URGENT! "
               
               batch_time_info = (
                   f"{urgency}Current batch is OPEN! Orders for the {batch_time_str} batch close in EXACTLY "
                   f"{minutes_remaining} minutes and {seconds_remaining} seconds. "
                   f"Complete your order by {batch_time_str} to get food at {food_time_str}. "
                   f"Late orders will automatically be moved to the next batch."
               )
           else:
               # Batch is not open yet - calculate time until it opens
               if current_time < batch_open_time:
                   # Before batch opens
                   time_diff = batch_open_time - current_time
                   minutes_until_open = int(time_diff.total_seconds() / 60)
                   seconds_until_open = int(time_diff.total_seconds() % 60)
                   
                   batch_time_str = batch_time.strftime("%I:%M %p")
                   food_time_str = food_ready_time.strftime("%I:%M %p")
                   open_time_str = batch_open_time.strftime("%I:%M %p")
                   
                   batch_time_info = (
                       f"The next batch opens at {open_time_str} (in {minutes_until_open} minutes and {seconds_until_open} seconds). "
                       f"Orders for the {batch_time_str} batch must be completed between {open_time_str} and {batch_time_str} "
                       f"to get food at {food_time_str}."
                   )
               else:
                   # After batch closes, calculate next batch
                   next_batch_time = batch_time + timedelta(minutes=30)
                   next_batch_open_time = batch_open_time + timedelta(minutes=30)
                   
                   if next_batch_open_time <= current_time:
                       # Next batch is already open
                       time_diff = next_batch_time - current_time
                       minutes_remaining = int(time_diff.total_seconds() / 60)
                       seconds_remaining = int(time_diff.total_seconds() % 60)
                       
                       next_batch_time_str = next_batch_time.strftime("%I:%M %p")
                       next_food_time_str = (next_batch_time + timedelta(minutes=30)).strftime("%I:%M %p")
                       
                       urgency = ""
                       if minutes_remaining < 5:
                           urgency = "🚨 URGENT! "
                       
                       batch_time_info = (
                           f"{urgency}Current batch is OPEN! Orders for the {next_batch_time_str} batch close in EXACTLY "
                           f"{minutes_remaining} minutes and {seconds_remaining} seconds. "
                           f"Complete your order by {next_batch_time_str} to get food at {next_food_time_str}. "
                           f"Late orders will automatically be moved to the next batch."
                       )
                   else:
                       # Waiting for next batch to open
                       time_diff = next_batch_open_time - current_time
                       minutes_until_open = int(time_diff.total_seconds() / 60)
                       seconds_until_open = int(time_diff.total_seconds() % 60)
                       
                       next_batch_time_str = next_batch_time.strftime("%I:%M %p")
                       next_food_time_str = (next_batch_time + timedelta(minutes=30)).strftime("%I:%M %p")
                       next_open_time_str = next_batch_open_time.strftime("%I:%M %p")
                       
                       batch_time_info = (
                           f"The next batch opens at {next_open_time_str} (in {minutes_until_open} minutes and {seconds_until_open} seconds). "
                           f"Orders for the {next_batch_time_str} batch must be completed between {next_open_time_str} and {next_batch_time_str} "
                           f"to get food at {next_food_time_str}."
                       )
       
       # Format hot restaurants information
       # Format hot restaurants information
       if batches and len(batches) > 0:
           hot_restaurants_info = "Current hot restaurants:\n"
           for batch in batches:
               restaurant = batch['restaurant_name']
               current_orders = batch['current_orders']
               max_orders = batch['max_orders']
               fee = batch['delivery_fee']
               free_item = batch.get('free_item', 'Free item')
               
               hot_restaurants_info += f"- {restaurant}: ${fee:.2f} delivery fee, {current_orders}/{max_orders} orders, Share & get {free_item}\n"
       # UPDATED SYSTEM PROMPT WITH NAME COLLECTION
       system_prompt = f"""
**TreeHouse SMS AI Assistant Prompt**
You are TreeHouse's friendly food delivery assistant, helping college students order food with a low $2-4 delivery fee. Your purpose is to guide customers through the batch ordering process, ensuring you collect all necessary information including the customer's order number from the restaurant.

CURRENT BATCH INFORMATION:
{batch_time_info}

**CRITICAL BATCH TIMING INFORMATION:**
* Ordering windows are EXACTLY 15 minutes long:
  - For XX:30 batches: Order between XX:15-XX:30 to get food at (XX+1):00
  - For XX:00 batches: Order between XX:45-XX:00 to get food at XX:30
* ALL deadlines are STRICT with NO exceptions
* Late orders will automatically be moved to the next batch
* This strict policy ensures food is delivered fresh and hot
* ALWAYS provide the EXACT minutes and seconds remaining in EVERY response

CURRENT HOT RESTAURANTS:
{hot_restaurants_info}

**Key Information About TreeHouse**
* TreeHouse offers $2-4 delivery fees (90% cheaper than competitors charging $14-18)
* We have 5 rotating restaurants every 30 minutes with guaranteed low delivery fees
* Orders delivered hourly - customers must order by :25-:30 to get food at the top of the next hour
* For building pickups: Food is delivered to designated pickup spots in those buildings
* For dorm orders: Pickup at the main entrance from a driver
* We deliver daily 24/7
* Sharing with friends gets both people free items when they join the same restaurant for the same batch

**CRITICAL: The TreeHouse Order Flow (ALWAYS FOLLOW THIS EXACT SEQUENCE)**
1. First, show available restaurants and current deals when a user asks about options
2. When the user indicates interest in a restaurant, explain that they need to place their order directly with the restaurant for pickup
3. Once they've placed their order with the restaurant, ask them to share their order number
4. If they don't have an order number, ask for their name so we can identify their order
5. Next, ask for their campus location for delivery
6. Finally instruct them to text PAY to complete their order with the delivery fee

**NEVER SKIP STEPS in this flow. Always collect either an order number or the customer's name - this is essential information.**

**Order Commands and Responses**

**1. When customer texts "MENU" or asks about options:**
Show the current batch information including:
* Available restaurants with location and batch time
* Current orders out of max capacity (e.g., "5/10 spots")
* Delivery fee for each restaurant
* Free item incentive for sharing 
Then prompt them to text ORDER followed by their restaurant choice.

**2. When customer expresses interest in ordering (e.g., "I want Chipotle"):**
Response: "Great! To order from Chipotle, please follow these steps:
1. Place your order directly with Chipotle's app/website/phone for PICKUP (not delivery)
2. When ordering, note it's for 'TreeHouse pickup'
3. After placing your order, text me 'ORDER Chipotle' with what you ordered, and I'll ask for your order confirmation number"

**3. When customer sends their order details:**
Response: "Great! Do you have an order confirmation number from Chipotle? This helps our driver pick up your order correctly."
* If they provide order number: "Thanks for providing your order number #[number]!"
* If no order number: "No problem. Can you please provide your name so our driver can identify your order when picking it up?"

**4. After getting the order number or customer name:**
Ask: "Where should we deliver this to on campus? (e.g., Student Center, University Hall, etc.)"

**5. After they provide location:**
Response: "Thanks! Your [Restaurant] order will be delivered to [Location]. You've joined the [Location] batch ([current]/[max] orders). Please pay the $4.00 delivery fee at [payment link]. Text PAY to get the payment link."

**6. When they text "PAY":**
Response: "Here's your payment link: [link]

IMPORTANT: If you already paid for your food through the restaurant's app/website (recommended), enter ONLY the $4.00 delivery fee.

If you ordered by phone and haven't paid for your food yet, enter the TOTAL amount including BOTH your food cost AND the $4.00 delivery fee."

**Additional Instructions**
* Always mention current batch timing and how much time is left to order (e.g., "Order by 1:25 PM to get food at 1:30 PM")
* Remind users to share with friends to get free items
* For each restaurant, consistently mention the free item they'll get for sharing
* Keep your responses friendly, concise, and helpful
* If a user skips steps, gently guide them back to the proper flow
* If uncertain about what to do, default to following the order flow steps in sequence

UNDERSTAND ALL COMMANDS:
- MENU or ??: Shows available restaurants
- ORDER [details]: Places an order
- PAY: Gets a payment link
- CANCEL: Cancels an order (within 10 minutes of ordering)
- HELP or INFO: Shows help information
- JOIN or START: Subscribes to messages
- STOP, CANCEL, UNSUBSCRIBE, END, or QUIT: Unsubscribes from messages

Your tone should be friendly, helpful, and efficient while maintaining the integrity of the ordering process. Always emphasize the importance of the order number or customer name for smooth pickup.
"""
       
       # Check conversation context to improve awareness of where we are in the ordering flow
       conversation_context = ""
       if user_history:
           # Analyze recent conversation to determine context
           recent_messages = user_history[-4:]  # Last 2 exchanges
           awaiting_location = False
           showed_menu = False
           awaiting_order_number = False
           awaiting_customer_name = False
           
           for entry in recent_messages:
               if entry['role'] == 'assistant' and "Just one more thing - please tell me which building or dorm you're in" in entry['content']:
                   awaiting_location = True
               if entry['role'] == 'assistant' and "TreeHouse Options" in entry['content']:
                   showed_menu = True
               if entry['role'] == 'assistant' and "Do you have an order confirmation number" in entry['content']:
                   awaiting_order_number = True
               if entry['role'] == 'assistant' and "please provide your name" in entry['content']:
                   awaiting_customer_name = True
           
           if awaiting_location:
               conversation_context += "USER CONTEXT: The user was recently asked for their location. If they respond with just a location name like 'University Hall' or a building name, interpret this as their location response.\n"
           
           if showed_menu:
               conversation_context += "USER CONTEXT: The user was recently shown the restaurant menu options. You can now help them place an order.\n"
               
           if awaiting_order_number:
               conversation_context += "USER CONTEXT: The user was recently asked for their order confirmation number. If they reply with just a number or code, interpret this as their order number. If they say they don't have one or ordered by phone, ask for their name instead.\n"
               
           if awaiting_customer_name:
               conversation_context += "USER CONTEXT: The user was asked for their name since they don't have an order number. If they reply with a name, acknowledge it and then ask for their location.\n"
       
       # Add the context to the system prompt
       if conversation_context:
           system_prompt += "\n" + conversation_context
       
       # Prepare conversation history if provided
       messages = [{"role": "system", "content": system_prompt}]
       
       if user_history:
           for entry in user_history[-8:]:  # Include more conversation history for better context
               if entry['role'] == 'user':
                   messages.append({"role": "user", "content": entry['content']})
               else:
                   messages.append({"role": "assistant", "content": entry['content']})
       
       # Add the current prompt
       messages.append({"role": "user", "content": prompt})
       
       # Call OpenAI API with increased temperature for more dynamic responses
       response = client.chat.completions.create(
           model="gpt-3.5-turbo",
           messages=messages,
           max_tokens=300,
           temperature=0.7
       )
       
       return response.choices[0].message.content
   
   except Exception as e:
       logger.error(f"Error using OpenAI for response generation: {e}")
       return "I'm having trouble processing that right now. Please try texting ORDER followed by what you want, or text MENU to see options."

def format_batch_info(batches):
    """Format the batch information for text message display"""
    if not batches:
        return "No current batches available. Please try again later."
    
    # Get the batch time from the first batch
    batch_time = datetime.fromisoformat(str(batches[0]['batch_time'])) if isinstance(batches[0]['batch_time'], str) else batches[0]['batch_time']
    batch_time_str = batch_time.strftime("%I:%M %p")
    
    # Calculate ordering window based on batch time
    current_time = datetime.now()
    
    # Determine if it's a XX:30 or XX:00 batch and calculate the open and close times
    if batch_time.minute == 30:  # XX:30 batch
        batch_open_time = datetime(batch_time.year, batch_time.month, batch_time.day, batch_time.hour, 15, 0)
        food_ready_time = batch_time + timedelta(minutes=30)  # Food ready at XX+1:00
        order_window = f"{batch_open_time.strftime('%I:%M')}-{batch_time.strftime('%I:%M %p')}"
    else:  # XX:00 batch
        batch_hour = batch_time.hour
        prev_hour = batch_hour - 1 if batch_hour > 0 else 23
        batch_open_time = datetime(batch_time.year, batch_time.month, batch_time.day, prev_hour, 45, 0)
        food_ready_time = batch_time + timedelta(minutes=30)  # Food ready at XX:30
        order_window = f"{batch_open_time.strftime('%I:%M')}-{batch_time.strftime('%I:%M %p')}"
    
    food_time_str = food_ready_time.strftime("%I:%M %p")
    
    # Format the response with strict ordering window
    response = f"TreeHouse Options (Order within the {order_window} window to get food at {food_time_str}):\n\n"
    
    for batch in batches:
        restaurant = batch['restaurant_name']
        current_orders = batch['current_orders']
        max_orders = batch['max_orders']
        fee = batch['delivery_fee']
        free_item = batch.get('free_item', 'Free item')
        
        response += f"- {restaurant} ({batch_time_str}) [${fee:.2f} fee, {current_orders}/{max_orders} spots] - Share & get {free_item}\n"
    
    response += "\n📱 IMPORTANT - HOW TO ORDER:\n"
    response += "1. First, place your order directly with the restaurant (via their app/website/phone) and select PICKUP (NOT DELIVERY)\n"
    response += "2. Then text \"ORDER\" followed by the restaurant name to us\n"
    response += "3. We'll ask for your order number/name and pickup location\n"
    response += "4. We'll pick up your order and deliver it to you for only $4!\n\n"
    response += "Share with a friend for you both to get free items when you order!"
    
    return response

def ai_process_order(order_text, phone_number):
   """
   Process an order request using AI
   Returns a tuple of (processed_text, restaurant_name, batch_info, is_complete_order)
   """
   # Check if this is just a location response (no restaurant name detection needed)
   # This handles replies to previous location requests
   if phone_number in active_sessions and active_sessions[phone_number].get('awaiting_location', False):
       # This is likely a location-only response
       location_info = order_text.strip()
       restaurant_name = active_sessions[phone_number].get('restaurant')
       
       # Save the location to the user profile
       conn = sqlite3.connect('treehouse.db')
       c = conn.cursor()
       c.execute("UPDATE users SET dorm_building = ? WHERE phone_number = ?", (location_info, phone_number))
       conn.commit()
       
       # Get the batch info that was previously stored
       batch = active_sessions[phone_number].get('batch_info')
       if not batch:
           # Retrieve batch info for the restaurant
           now = datetime.now()
           c.execute("""
               SELECT * FROM batch_tracking 
               WHERE restaurant_name = ? AND batch_time > ? 
               ORDER BY batch_time ASC 
               LIMIT 1
           """, (restaurant_name, now))
           
           batch_row = c.fetchone()
           if batch_row:
               batch = dict(batch_row)
       
       # Clear the awaiting_location flag
       active_sessions[phone_number]['awaiting_location'] = False
       active_sessions[phone_number]['location'] = location_info
       
       # Create response with location acknowledgment
       batch_time = datetime.fromisoformat(str(batch['batch_time'])) if isinstance(batch['batch_time'], str) else batch['batch_time']
       batch_time_str = batch_time.strftime("%I:%M %p")
       
       # Get free item info
       free_item = None
       for restaurant in hot_restaurants:
           if restaurant['name'] == restaurant_name:
               free_item = restaurant['freeItem']
               break
       
       if not free_item:
           for restaurant in other_restaurants:
               if restaurant['name'] == restaurant_name:
                   free_item = restaurant['freeItem']
                   break
       
       response = (
           f"Thanks! Your {restaurant_name} order will be delivered to {location_info}. "
           f"You've joined the {batch['location']} batch "
           f"({batch['current_orders']}/{batch['max_orders']} orders).\n\n"
           f"Pickup at {batch_time_str}.\n"
           f"Text 'PAY' to get your payment link (enter ONLY the $4.00 delivery fee if you've already paid for your food through {restaurant_name}'s app/website).\n\n"
           f"Share this text and you both get {free_item}: \"Join me for {restaurant_name}! "
           f"Text (844) 311-8208 to order with TreeHouse and save 90% on delivery!\""
       )
       
       conn.close()
       return response, restaurant_name, batch, True
   
   # Check if this is a customer name response
   if phone_number in active_sessions and active_sessions[phone_number].get('awaiting_customer_name', False):
       # Process the customer name
       customer_name = order_text.strip()
       restaurant_name = active_sessions[phone_number].get('restaurant')
       
       # Save the customer name
       active_sessions[phone_number]['customer_name'] = customer_name
       active_sessions[phone_number]['awaiting_customer_name'] = False
       
       # Update the database with the customer name
       conn = sqlite3.connect('treehouse.db')
       c = conn.cursor()
       c.execute("UPDATE users SET name = ? WHERE phone_number = ?", (customer_name, phone_number))
       conn.commit()
       conn.close()
       
       # Now ask for location
       active_sessions[phone_number]['awaiting_location'] = True
       
       return (
           f"Thanks {customer_name}! Now, where should we deliver your {restaurant_name} order to? "
           f"(e.g., Student Center, University Hall, etc.)",
           restaurant_name,
           None,
           False
       )
   
   # Check if this is a response to an order number request
   if phone_number in active_sessions and active_sessions[phone_number].get('awaiting_order_number', False):
       restaurant_name = active_sessions[phone_number].get('restaurant')
       
       # Check if they're saying they don't have an order number
       if any(phrase in order_text.lower() for phrase in ["no", "don't have", "ordered by phone", "phone order"]):
           # They don't have an order number, ask for their name
           active_sessions[phone_number]['awaiting_order_number'] = False
           active_sessions[phone_number]['awaiting_customer_name'] = True
           
           return (
               f"No problem. Can you please provide your name so our driver can identify your {restaurant_name} order when picking it up?",
               restaurant_name,
               None,
               False
           )
       # Check if they're saying "yes" they have an order number but haven't provided it
       elif any(phrase in order_text.lower() for phrase in ["yes", "yeah", "yep", "sure", "i do"]) and len(order_text.strip()) < 10:
           # They indicated yes but didn't provide the number
           return (
               f"Great! Please send me your order confirmation number from {restaurant_name} so our driver can identify your order correctly.",
               restaurant_name,
               None,
               False
           )
       else:
           # They're providing an order number
           order_number = order_text.strip()
           active_sessions[phone_number]['order_number'] = order_number
           active_sessions[phone_number]['awaiting_order_number'] = False
           
           # Now ask for location
           active_sessions[phone_number]['awaiting_location'] = True
           
           return (
               f"Thanks for providing your order number {order_number}! Now, where should we deliver your {restaurant_name} order to? "
               f"(e.g., Student Center, University Hall, etc.)",
               restaurant_name,
               None,
               False
           )
   
   # Original order processing flow
   # Extract restaurant from order text
   restaurant_name, processed_order = extract_restaurant_from_order(order_text)
   
   if not restaurant_name:
       return (
           "I couldn't determine which restaurant you want to order from. "
           "Please specify a restaurant in your order, like 'ORDER a burrito from Chipotle'.",
           None,
           None,
           False
       )
   
   # Check if the order text is too generic (just mentioning restaurant name with no specific items)
   # We don't need specific food items since we'll identify the order by order number or customer name
   words = order_text.split()
   if len(words) < 2 or (restaurant_name.lower() in order_text.lower() and len(order_text) < len(restaurant_name) + 5):
       # Still make sure they've provided at least a restaurant name
       processed_order = f"Order from {restaurant_name}"
   else:
       processed_order = order_text
       
   # Get batch information first (for both paths)
   now = datetime.now()
   conn = sqlite3.connect('treehouse.db')
   conn.row_factory = sqlite3.Row
   c = conn.cursor()
   
   c.execute("""
       SELECT * FROM batch_tracking 
       WHERE restaurant_name = ? AND batch_time > ? 
       ORDER BY batch_time ASC 
       LIMIT 1
   """, (restaurant_name, now))
   
   batch_row = c.fetchone()
   
   if not batch_row:
       # No batch found, create one
       init_restaurant_batches()
       
       # Try again
       c.execute("""
           SELECT * FROM batch_tracking 
           WHERE restaurant_name = ? AND batch_time > ? 
           ORDER BY batch_time ASC 
           LIMIT 1
       """, (restaurant_name, now))
       
       batch_row = c.fetchone()
   
   # Create batch dict
   batch = dict(batch_row) if batch_row else None
   
   # First ask for order number instead of location
   if phone_number not in active_sessions:
       active_sessions[phone_number] = {}
   
   active_sessions[phone_number]['restaurant'] = restaurant_name
   active_sessions[phone_number]['order_text'] = processed_order
   active_sessions[phone_number]['started_at'] = now
   active_sessions[phone_number]['awaiting_order_number'] = True
   
   if batch:
       active_sessions[phone_number]['batch_info'] = batch
   
   conn.close()
   
   return (
   f"Great! To order from {restaurant_name}, please follow these steps:\n\n"
   f"1. First, place your order directly with {restaurant_name}'s app/website/phone and select PICKUP option (not delivery)\n"
   f"2. Once you've placed your order, come back and let me know your order confirmation number\n\n"
   f"Have you already placed your order with {restaurant_name}? If so, do you have your order confirmation number? If you don't have an order number or if {restaurant_name} doesn't provide one, just let me know your name instead.",
   restaurant_name,
   None,
   False
)

# Updated menu detection function
def is_menu_request(message):
    message_lower = message.lower()
    
    # Skip specific command words
    command_words = ['pay', 'order', 'cancel', 'help', 'info', 'join', 'start', 'stop', 'quit']
    first_word = message_lower.split(' ')[0]
    if first_word in command_words:
        return False
    
    # Direct menu requests that should show the formatted menu
    direct_menu_keywords = [
        'menu', 'restaurants', 'options', 'deals now', 'current deals',
        'what restaurants', 'available restaurants', 'show me restaurants',
        'what is available', 'what are the options', 'ordering time', 'time to order',
        'batch time', 'food time', 'delivery time', 'batch open', 'when can i order'
    ]
    
    # Check for direct menu requests
    for phrase in direct_menu_keywords:
        if phrase in message_lower:
            return True
            
    # Check for single affirmative responses that might follow a menu offer
    if len(message_lower.split()) <= 2 and any(word in message_lower for word in [
        'yes', 'yeah', 'sure', 'ok', 'okay', 'please', 'y', 'yep', 'yup'
    ]):
        return True
            
    return False


def process_batch_delivery(batch_id):
    """
    Process a batch delivery using Uber Direct
    
    Args:
        batch_id: ID of the batch to process
        
    Returns:
        str: Status of the processing
    """
    # Check if Uber Direct integration is available
    if not UBER_DIRECT_AVAILABLE:
        logger.error("Cannot process delivery: Uber Direct module not available")
        return "Error: Uber Direct module not available"
    
    # Load Uber Direct API credentials from environment variables
    api_credentials = {
        "client_id": os.getenv('UBER_CLIENT_ID'),
        "client_secret": os.getenv('UBER_CLIENT_SECRET'),
        "customer_id": os.getenv('UBER_CUSTOMER_ID')
    }
    
    # Check if credentials are available
    if not all(api_credentials.values()):
        logger.error("Uber Direct API credentials not configured")
        return "Error: Uber Direct API credentials not configured"
    
    # Connect to database
    conn = sqlite3.connect('treehouse.db')
    conn.row_factory = sqlite3.Row
    
    try:
        # Prepare batch data for delivery
        batch_data = prepare_batch_for_delivery(batch_id, conn)
        
        # Check if we have any restaurants with orders
        if not batch_data.get('restaurants'):
            logger.info(f"Batch {batch_id} has no restaurant orders to process")
            conn.close()
            return "No orders to process"
        
        # Create Uber Direct client
        uber_direct = UberDirectDelivery(
            client_id=api_credentials["client_id"],
            client_secret=api_credentials["client_secret"],
            customer_id=api_credentials["customer_id"],
            test_mode=True  # Set to False for production
        )
        
        # Process the batch
        deliveries = uber_direct.process_batch(batch_data)
        
        # Update order statuses in database
        c = conn.cursor()
        for restaurant, delivery_data in deliveries.items():
            for order in delivery_data["orders"]:
                c.execute(
                    "UPDATE orders SET status = 'in_delivery' WHERE id = ?",
                    (order["order_id"],)
                )
                
                # Send tracking URL to customer
                if twilio_client and 'delivery' in delivery_data and 'tracking_url' in delivery_data['delivery']:
                    try:
                        # Get customer phone number
                        c.execute("""
                            SELECT u.phone_number 
                            FROM users u 
                            JOIN orders o ON u.id = o.user_id 
                            WHERE o.id = ?
                        """, (order["order_id"],))
                        
                        user_result = c.fetchone()
                        if user_result and user_result[0]:
                            user_phone = user_result[0]
                            tracking_message = (
                                f"Your {restaurant} order is now with Uber! "
                                f"Track your delivery here: {delivery_data['delivery']['tracking_url']}\n\n"
                                f"Your food will arrive at {delivery_data['destination']} shortly."
                            )
                            
                            twilio_client.messages.create(
                                body=tracking_message,
                                from_=twilio_phone,
                                to=f"+{user_phone}"
                            )
                    except Exception as e:
                        logger.error(f"Error sending tracking URL: {e}")
        
        # Update batch status
        c.execute(
            "UPDATE delivery_batches SET status = 'in_progress' WHERE id = ?",
            (batch_id,)
        )
        
        conn.commit()
        
        # Send admin notification
        if twilio_client:
            try:
                admin_notification = (
                    f"Batch {batch_id} processed!\n\n"
                    f"Delivery set for {batch_data['location']}\n"
                    f"Restaurants: {', '.join(deliveries.keys())}\n"
                    f"Total orders: {sum(len(data['orders']) for _, data in deliveries.items())}"
                )
                
                twilio_client.messages.create(
                    body=admin_notification,
                    from_=twilio_phone,
                    to=notification_email
                )
            except Exception as e:
                logger.error(f"Error sending admin notification: {e}")
        
        return "Success"
    
    except Exception as e:
        logger.error(f"Error processing batch delivery: {e}")
        if 'conn' in locals() and conn:
            conn.rollback()
        raise
    finally:
        if 'conn' in locals() and conn:
            conn.close()


# Initialize the scheduler
scheduler = BackgroundScheduler()

def check_and_process_batches():
    """
    Check for batches that have closed and need to be processed for delivery
    This function runs every minute to find batches that have reached their time
    """
    try:
        now = datetime.now()
        logger.info(f"Running scheduled batch check at {now}")
        
        # Connect to database
        conn = sqlite3.connect('treehouse.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # Find batches where:
        # 1. The batch time has passed (window closed)
        # 2. Status is still 'scheduled' (not yet processed)
        # 3. Has at least one order
        c.execute("""
            SELECT db.id, db.delivery_time, 
                  (SELECT COUNT(*) FROM batch_orders WHERE batch_id = db.id) AS order_count
            FROM delivery_batches db
            WHERE db.delivery_time <= ? 
              AND db.status = 'scheduled'
              AND (SELECT COUNT(*) FROM batch_orders WHERE batch_id = db.id) > 0
            ORDER BY db.delivery_time
        """, (now,))
        
        batches = c.fetchall()
        conn.close()
        
        if not batches:
            logger.info("No batches ready for delivery")
            return
        
        # Process each batch that's ready
        for batch in batches:
            batch_id = batch['id']
            batch_time = batch['delivery_time']
            order_count = batch['order_count']
            
            # Only process if there are orders in this batch
            if order_count > 0:
                try:
                    logger.info(f"Auto-processing batch {batch_id} with {order_count} orders")
                    result = process_batch_delivery(batch_id)
                    logger.info(f"Successfully processed batch {batch_id}: {result}")
                except Exception as e:
                    logger.error(f"Error processing batch {batch_id}: {e}")
            else:
                logger.info(f"Skipping empty batch {batch_id}")
    
    except Exception as e:
        logger.error(f"Error in batch check scheduler: {e}")

# Schedule the task to run every minute
scheduler.add_job(
    func=check_and_process_batches,
    trigger="interval",
    minutes=1
)

# Start the scheduler
def start_scheduler():
    scheduler.start()
    logger.info("Started batch processing scheduler")

# Shut down the scheduler when the app stops
def stop_scheduler():
    scheduler.shutdown()
    logger.info("Stopped batch processing scheduler")

# Register the shutdown function
atexit.register(stop_scheduler)


@app.route('/webhook/sms', methods=['POST'])
def sms_webhook():
    # Get the incoming message details
    incoming_message = request.values.get('Body', '').strip()
    from_number = request.values.get('From', '')
    
    # Clean the phone number
    clean_phone = ''.join(filter(str.isdigit, from_number))
    
    # Create a TwiML response
    resp = MessagingResponse()
    
    # Handle STOP, UNSUBSCRIBE commands (opt-out)
    if incoming_message.upper() in ['STOP', 'CANCEL', 'UNSUBSCRIBE', 'END', 'QUIT']:
        try:
            conn = sqlite3.connect('treehouse.db')
            c = conn.cursor()
            
            # Update user's consent status
            c.execute("UPDATE users SET sms_consent = 0 WHERE phone_number = ?", (clean_phone,))
            conn.commit()
            
            # Find user ID for logging purposes
            c.execute("SELECT id FROM users WHERE phone_number = ?", (clean_phone,))
            user = c.fetchone()
            conn.close()
            
            # Send confirmation message
            resp.message("You have been unsubscribed from TreeHouse messages. Text JOIN to resubscribe at any time.")
            logger.info(f"User {from_number} opted out of messages")
            
            # Remove from active sessions if present
            if clean_phone in active_sessions:
                del active_sessions[clean_phone]
            
            return str(resp)
        except Exception as e:
            logger.error(f"Error processing opt-out: {e}")
    
    # Handle HELP command
    elif incoming_message.upper() == 'HELP':
        help_text = (
            "TreeHouse - Restaurant delivery for ONLY $4!\n\n"
            "Commands:\n"
            "• MENU - See available restaurants\n"
            "• ORDER [details] - Place an order\n"
            "• PAY - Get a payment link\n"
            "• STOP - Unsubscribe from messages\n\n"
            "For assistance, call (708) 901-1754\n"
            "Msg & data rates may apply."
        )
        resp.message(help_text)
        return str(resp)
    
    # Handle JOIN or START for resubscribing
    elif incoming_message.upper() in ['JOIN', 'START']:
        try:
            conn = sqlite3.connect('treehouse.db')
            c = conn.cursor()
            
            # Check if user exists
            c.execute("SELECT id FROM users WHERE phone_number = ?", (clean_phone,))
            user = c.fetchone()
            
            if user:
                # Update consent status
                c.execute("UPDATE users SET sms_consent = 1, opt_in_timestamp = ? WHERE phone_number = ?", 
                         (datetime.now().isoformat(), clean_phone))
                conn.commit()
                conn.close()
                
                # Send confirmation message
                resp.message("Welcome back to TreeHouse! You're now subscribed to receive messages. Text MENU to see restaurant options.")
                logger.info(f"User {from_number} opted back in to messages")
                return str(resp)
            else:
                # New user - create an account
                c.execute("INSERT INTO users (phone_number, sms_consent, opt_in_timestamp) VALUES (?, ?, ?)",
                         (clean_phone, True, datetime.now().isoformat()))
                conn.commit()
                conn.close()
                
                resp.message("Welcome to TreeHouse! You're now subscribed to receive messages. Text MENU to see restaurant options.")
                logger.info(f"New user {from_number} joined via text")
                return str(resp)
        except Exception as e:
            logger.error(f"Error processing opt-in: {e}")
    
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
    
    # Get user history for AI context
    user_history = []
    if clean_phone in active_sessions and 'conversation_history' in active_sessions[clean_phone]:
        user_history = active_sessions[clean_phone]['conversation_history']
    else:
        # Initialize conversation history
        active_sessions[clean_phone] = active_sessions.get(clean_phone, {})
        active_sessions[clean_phone]['conversation_history'] = []
        active_sessions[clean_phone]['user_id'] = user_id
    
    # Check if this is a location-only response to a previous question
    if clean_phone in active_sessions and active_sessions[clean_phone].get('awaiting_location', False):
        # This looks like a location response, process it as an order continuation
        logger.info(f"Processing location response from {from_number}: {incoming_message}")
        
        # Get the stored restaurant and order
        restaurant_name = active_sessions[clean_phone].get('restaurant')
        order_text = active_sessions[clean_phone].get('order_text')
        
        if restaurant_name:
            # Process as a continuation of the order with the location
            ai_response, restaurant, batch_info, is_complete_order = ai_process_order(incoming_message, clean_phone)
            
            # Update conversation history
            user_history.append({'role': 'user', 'content': incoming_message})
            user_history.append({'role': 'assistant', 'content': ai_response})
            active_sessions[clean_phone]['conversation_history'] = user_history
            
            resp.message(ai_response)
            logger.info(f"Processed location response for order from {from_number} using TwiML")
            
            # Send admin notification if order is now complete
            if is_complete_order and twilio_client:
                try:
                    # Get user details
                    c.execute("SELECT name, dorm_building, room_number FROM users WHERE id = ?", (user_id,))
                    user_details = c.fetchone()
                    user_name = user_details[0] if user_details and user_details[0] else "Unknown"
                    dorm = user_details[1] if user_details and user_details[1] else "Unknown"
                    room = user_details[2] if user_details and user_details[2] else "Unknown"
                    
                    # Build notification with the location
                    admin_note = f"⚠️ NEW ORDER WITH LOCATION! #{random.randint(1000, 9999)}\n\n"
                    admin_note += f"Customer: {user_name} ({from_number})\n"
                    
                    # Add customer-provided name if available
                    if 'customer_name' in active_sessions[clean_phone]:
                        admin_note += f"Customer Name for Order: {active_sessions[clean_phone]['customer_name']}\n"

                    # Add order number if available
                    if 'order_number' in active_sessions[clean_phone]:
                        admin_note += f"Order Number: {active_sessions[clean_phone]['order_number']}\n"
                    
                    admin_note += f"LOCATION: {dorm}, Room {room}\n\n"
                    admin_note += f"Restaurant: {restaurant_name}\n"
                    admin_note += f"Order: {order_text}\n\n"
                    admin_note += "Customer will need to text 'PAY' to receive payment link."
                    
                    twilio_message = twilio_client.messages.create(
                        body=admin_note,
                        from_=twilio_phone,
                        to=notification_email
                    )
                    logger.info(f"Admin notification sent for completed order with location: {twilio_message.sid}")
                except Exception as e:
                    logger.error(f"Error sending admin notification for location update: {e}")
            
            conn.close()
            return str(resp)
    
    # Check if this is a response to an order number request
    elif clean_phone in active_sessions and active_sessions[clean_phone].get('awaiting_order_number', False):
        logger.info(f"Processing order number response from {from_number}: {incoming_message}")
        
        # Get the stored restaurant and order
        restaurant_name = active_sessions[clean_phone].get('restaurant')
        order_text = active_sessions[clean_phone].get('order_text')
        
        # Check if they're saying they don't have an order number
        if any(phrase in incoming_message.lower() for phrase in ["no", "don't have", "ordered by phone", "phone order"]):
            # They don't have an order number, ask for their name
            active_sessions[clean_phone]['awaiting_order_number'] = False
            active_sessions[clean_phone]['awaiting_customer_name'] = True
            
            response = f"No problem. Can you please provide your name so our driver can identify your {restaurant_name} order when picking it up?"
            
            # Update conversation history
            user_history.append({'role': 'user', 'content': incoming_message})
            user_history.append({'role': 'assistant', 'content': response})
            active_sessions[clean_phone]['conversation_history'] = user_history
            
            resp.message(response)
            logger.info(f"Asked for customer name after no order number from {from_number}")
            
            conn.close()
            return str(resp)
        else:
            # They're providing an order number
            order_number = incoming_message.strip()
            active_sessions[clean_phone]['order_number'] = order_number
            active_sessions[clean_phone]['awaiting_order_number'] = False
            
            # Now ask for location
            active_sessions[clean_phone]['awaiting_location'] = True
            
            response = f"Thanks for providing your order number {order_number}! Now, where should we deliver your {restaurant_name} order to? (e.g., Student Center, University Hall, etc.)"
            
            # Update conversation history
            user_history.append({'role': 'user', 'content': incoming_message})
            user_history.append({'role': 'assistant', 'content': response})
            active_sessions[clean_phone]['conversation_history'] = user_history
            
            resp.message(response)
            logger.info(f"Processed order number from {from_number}: {order_number}")
            
            conn.close()
            return str(resp)

    # Check if this is a customer name response
    elif clean_phone in active_sessions and active_sessions[clean_phone].get('awaiting_customer_name', False):
        logger.info(f"Processing customer name response from {from_number}: {incoming_message}")
        
        # Extract the customer name from the message
        customer_name = incoming_message.strip()
        
        # Get the stored restaurant and order
        restaurant_name = active_sessions[clean_phone].get('restaurant')
        order_text = active_sessions[clean_phone].get('order_text')
        
        if restaurant_name:
            # Store the customer name in the active session and in the database
            active_sessions[clean_phone]['customer_name'] = customer_name
            active_sessions[clean_phone]['awaiting_customer_name'] = False
            
            # Update user's name in the database
            try:
                c.execute("UPDATE users SET name = ? WHERE phone_number = ?", (customer_name, clean_phone))
                conn.commit()
            except Exception as e:
                logger.error(f"Error updating customer name in database: {e}")
            
            # Ask for location next
            response = f"Thanks {customer_name}! Now, where should we deliver your {restaurant_name} order to? (e.g., Student Center, University Hall, etc.)"
            
            # Set awaiting_location to get location in the next response
            active_sessions[clean_phone]['awaiting_location'] = True
            
            # Update conversation history
            user_history.append({'role': 'user', 'content': incoming_message})
            user_history.append({'role': 'assistant', 'content': response})
            active_sessions[clean_phone]['conversation_history'] = user_history
            
            resp.message(response)
            logger.info(f"Processed customer name response from {from_number} using TwiML")
            
            conn.close()
            return str(resp)
    
    # Process command based on the first word (lowercase for case insensitivity)
    first_word = incoming_message.split(' ')[0].lower()
    
    # Check for exact direct commands first
    if first_word == 'menu' or first_word == 'restaurants' or is_menu_request(incoming_message):
        # Get current batches
        batches = get_current_batches()
        response = format_batch_info(batches)
        
        # Add welcome message if needed
        if welcome_msg:
            response = welcome_msg + response
        
        # Update conversation history
        user_history.append({'role': 'user', 'content': incoming_message})
        user_history.append({'role': 'assistant', 'content': response})
        active_sessions[clean_phone]['conversation_history'] = user_history
        
        resp.message(response)
        logger.info(f"Sent restaurant list to {from_number} using TwiML")
        
    elif first_word == 'order':
        # Process order with free-form text
        if len(incoming_message) <= 6:  # Just "order" with no details
            response = "Please tell us what you'd like to order by texting 'ORDER' followed by your items. For example: 'ORDER 2 burritos from Chipotle with guac and chips'"
        else:
            # Extract order text (everything after "order ")
            order_text = incoming_message[6:].strip()
            
            # Process the order with AI
            ai_response, restaurant_name, batch_info, is_complete_order = ai_process_order(order_text, clean_phone)
            
            # Save the order in the session
            if clean_phone not in active_sessions:
                import datetime as dt
                active_sessions[clean_phone] = {
                    'user_id': user_id,
                    'order_text': order_text,
                    'started_at': dt.datetime.now()
                }
                if restaurant_name:
                    active_sessions[clean_phone]['restaurant'] = restaurant_name
                if batch_info:
                    active_sessions[clean_phone]['batch_info'] = batch_info
            else:
                active_sessions[clean_phone]['order_text'] = order_text
                if restaurant_name:
                    active_sessions[clean_phone]['restaurant'] = restaurant_name
                if batch_info:
                    active_sessions[clean_phone]['batch_info'] = batch_info
            
            # Send notification to admin ONLY for complete orders
            if twilio_client and restaurant_name and is_complete_order:
                try:
                    # Get user details if available
                    c.execute("SELECT name, dorm_building, room_number FROM users WHERE id = ?", (user_id,))
                    user_details = c.fetchone()
                    user_name = user_details[0] if user_details and user_details[0] else "Unknown"
                    dorm = user_details[1] if user_details and user_details[1] else "Unknown"
                    room = user_details[2] if user_details and user_details[2] else "Unknown"
                    
                    # Build the notification - Make this more visible
                    admin_note = f"⚠️ NEW TEXT ORDER RECEIVED! #{random.randint(1000, 9999)}\n\n"
                    admin_note += f"Customer: {user_name} ({from_number})\n"
                    
                    # Add customer-provided name if available
                    if 'customer_name' in active_sessions[clean_phone]:
                        admin_note += f"Customer Name for Order: {active_sessions[clean_phone]['customer_name']}\n"

                    # Add order number if available
                    if 'order_number' in active_sessions[clean_phone]:
                        admin_note += f"Order Number: {active_sessions[clean_phone]['order_number']}\n"
                    
                    admin_note += f"LOCATION: {dorm}, Room {room}\n\n"  # Make location stand out
                    admin_note += f"Restaurant: {restaurant_name}\n"
                    admin_note += f"Order: {order_text}\n\n"
                    admin_note += "Customer will need to text 'PAY' to receive payment link."
                    
                    # Make sure you're using the right Twilio client and notification number
                    twilio_message = twilio_client.messages.create(
                        body=admin_note,
                        from_=twilio_phone,
                        to=notification_email  # Make sure this is your phone number in E.164 format
                    )
                    logger.info(f"Admin notification sent for new text order from {from_number}: {twilio_message.sid}")
                except Exception as e:
                    logger.error(f"Error sending admin notification: {e}")

                # Debug logging to help diagnose issues with admin notifications
                logger.info(f"Variables for admin notification: twilio_client exists: {twilio_client is not None}, " + 
                           f"restaurant_name: '{restaurant_name}', is_complete_order: {is_complete_order}, " +
                           f"notification_email: '{notification_email}'")
            
            # Set the response
            response = ai_response
            
            # Update conversation history
            user_history.append({'role': 'user', 'content': incoming_message})
            user_history.append({'role': 'assistant', 'content': response})
            active_sessions[clean_phone]['conversation_history'] = user_history
            
            resp.message(response)
            logger.info(f"Processed order request from {from_number} using TwiML")
        
    elif first_word == 'pay':
        # Check if they have an active order
        has_active_order = clean_phone in active_sessions
        
        # Get delivery fee from batch info if available
        delivery_fee = 4.00  # Default
        if has_active_order and 'batch_info' in active_sessions[clean_phone]:
            batch_info = active_sessions[clean_phone]['batch_info']
            if batch_info and 'delivery_fee' in batch_info:
                delivery_fee = float(batch_info['delivery_fee'])
        
        # Use the fixed payment link from your Stripe dashboard
        payment_link = "https://buy.stripe.com/4gweYm6zB6FbfbWdQQ"
        
        # Generate a unique session ID for tracking
        import datetime as dt
        payment_session_id = f"pay_{clean_phone}_{int(dt.datetime.now().timestamp())}"
        
        # Store the session ID in the active session
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
        response += f"IMPORTANT: If you already paid for your food through the restaurant's app/website (recommended), enter ONLY the $4.00 delivery fee.\n\n"
        response += f"If you ordered by phone and haven't paid for your food yet, enter the TOTAL amount including BOTH your food cost AND the $4.00 delivery fee. For example, if your food costs $15, enter $19.00 total."
        if has_active_order:
            order_text = active_sessions[clean_phone].get('order_text', '')
            restaurant = active_sessions[clean_phone].get('restaurant', '')
            
            # Safely format batch time if it exists
            batch_time_str = None
            
            if 'batch_info' in active_sessions[clean_phone]:
                batch_info = active_sessions[clean_phone]['batch_info']
                if batch_info and 'batch_time' in batch_info:
                    batch_time = batch_info['batch_time']
                    # Safely convert batch_time to string format
                    if isinstance(batch_time, datetime):
                        batch_time_str = batch_time.strftime("%I:%M %p")
                    elif isinstance(batch_time, str):
                        try:
                            dt_obj = datetime.fromisoformat(batch_time.replace('Z', '+00:00'))
                            batch_time_str = dt_obj.strftime("%I:%M %p")
                        except:
                            # If parsing fails, just use the string itself
                            batch_time_str = batch_time
            
            response += f"\n\nFor reference, your order was: {order_text}"
            
            if restaurant and batch_time_str:
                response += f"\nRestaurant: {restaurant}, Pickup at {batch_time_str}"
        
        # Update conversation history
        user_history.append({'role': 'user', 'content': incoming_message})
        user_history.append({'role': 'assistant', 'content': response})
        active_sessions[clean_phone]['conversation_history'] = user_history
        
        resp.message(response)
        logger.info(f"Sent payment link to {from_number} using TwiML")
        
        # Send notification to admin
        if twilio_client:
            try:
                admin_note = f"PAYMENT REQUESTED!\n\n"
                admin_note += f"Customer: {from_number}\n"
                if has_active_order:
                    restaurant = active_sessions[clean_phone].get('restaurant', 'Unknown')
                    admin_note += f"Restaurant: {restaurant}\n"
                    admin_note += f"Order: {active_sessions[clean_phone].get('order_text', 'No order text')}\n"
                else:
                    admin_note += "Note: Customer likely called in their order\n"
                admin_note += f"Session ID: {payment_session_id}"
                
                twilio_client.messages.create(
                    body=admin_note,
                    from_=twilio_phone,
                    to=notification_email
                )
            except Exception as e:
                logger.error(f"Error sending admin notification: {e}")
    
    elif first_word in ['help', 'info']:
        # Provide help information
        response = "TreeHouse - Restaurant delivery for ONLY $4!\n\n"
        response += "Commands:\n"
        response += "• Text 'MENU' to see available restaurants\n"
        response += "• Text 'ORDER' followed by what you want (e.g., 'ORDER 2 burritos from Chipotle')\n"
        response += "• Text 'PAY' to get a payment link\n"
        response += "• Call (708) 901-1754 for special orders or questions\n\n"
        response += "Food is delivered hourly. Order by :25-:30 of each hour to get your food at the top of the next hour."
        
        # Update conversation history
        user_history.append({'role': 'user', 'content': incoming_message})
        user_history.append({'role': 'assistant', 'content': response})
        active_sessions[clean_phone]['conversation_history'] = user_history
        
        resp.message(response)
        logger.info(f"Sent help info to {from_number} using TwiML")
    
    elif first_word == 'cancel':
        # Handle order cancellation
        if clean_phone in active_sessions and 'order_text' in active_sessions[clean_phone]:
            # Check if there's a time limit on cancellation (e.g., 10 minutes after ordering)
            now = datetime.now()
            started_at = active_sessions[clean_phone].get('started_at')
            
            if started_at and (now - started_at).total_seconds() <= 600:  # 10 minutes
                # Cancel the order
                restaurant = active_sessions[clean_phone].get('restaurant', 'Unknown')
                
                # Remove the order from the batch count if possible
                if 'batch_info' in active_sessions[clean_phone]:
                    batch_info = active_sessions[clean_phone]['batch_info']
                    try:
                        conn = sqlite3.connect('treehouse.db')
                        c = conn.cursor()
                        c.execute("""
                            UPDATE batch_tracking 
                            SET current_orders = current_orders - 1 
                            WHERE id = ? AND current_orders > 0
                        """, (batch_info['id'],))
                        conn.commit()
                        conn.close()
                    except Exception as e:
                        logger.error(f"Error updating batch count for cancellation: {e}")
                
                # Clear the order from the session
                active_sessions[clean_phone].pop('order_text', None)
                active_sessions[clean_phone].pop('restaurant', None)
                active_sessions[clean_phone].pop('batch_info', None)
                
                response = f"Your {restaurant} order has been cancelled. If you'd like to place a new order, text 'MENU' to see options."
                
                # Notify admin about cancellation
                if twilio_client:
                    try:
                        admin_note = f"ORDER CANCELLED!\n\n"
                        admin_note += f"Customer: {from_number}\n"
                        admin_note += f"Restaurant: {restaurant}\n"
                        
                        twilio_client.messages.create(
                            body=admin_note,
                            from_=twilio_phone,
                            to=notification_email
                        )
                    except Exception as e:
                        logger.error(f"Error sending admin notification for cancellation: {e}")
            else:
                # Too late to cancel
                response = "Sorry, it's too late to cancel your order. Orders can only be cancelled within 10 minutes of placing them."
        else:
            # No active order to cancel
            response = "You don't have an active order to cancel. Text 'MENU' to see restaurant options and place a new order."
        
        # Update conversation history
        user_history.append({'role': 'user', 'content': incoming_message})
        user_history.append({'role': 'assistant', 'content': response})
        active_sessions[clean_phone]['conversation_history'] = user_history
        
        resp.message(response)
        logger.info(f"Processed cancellation request from {from_number}")
    
    else:
        # Process general message with AI assistance
        # Check if OpenAI API is available
        if openai_api_key:
            # Use the improved AI response function that maintains better order flow
            response = ai_generate_response(incoming_message, user_history)
            
            # Add a suggestion to use primary commands if not mentioned
            if not any(keyword in response.lower() for keyword in ['menu', 'order', 'pay']):
                response += "\n\nText 'MENU' to see restaurant options or 'ORDER' followed by what you want."
        else:
            # Fallback response without AI
            response = "I didn't understand that command. Text 'MENU' to see restaurants, 'ORDER' followed by what you want, or 'PAY' to get a payment link. Need help? Text 'HELP' or call (708) 901-1754."
        
        # Update conversation history
        user_history.append({'role': 'user', 'content': incoming_message})
        user_history.append({'role': 'assistant', 'content': response})
        active_sessions[clean_phone]['conversation_history'] = user_history
        
        resp.message(response)
        logger.info(f"Sent AI-powered response to {from_number} using TwiML")
    
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
    
    # Initialize conversation history in session if it doesn't exist
    if clean_phone not in active_sessions or 'conversation_history' not in active_sessions[clean_phone]:
        active_sessions[clean_phone] = active_sessions.get(clean_phone, {})
        active_sessions[clean_phone]['conversation_history'] = []
        active_sessions[clean_phone]['user_id'] = user_id
    
    user_history = active_sessions[clean_phone]['conversation_history']
    
    # Handle the message based on content
    lower_message = test_message.lower()
    first_word = lower_message.split(' ')[0]
    
    if first_word in ['menu', 'restaurants']:
        # Display restaurant list with links
        batches = get_current_batches()
        response = format_batch_info(batches)
        
        # Update conversation history
        user_history.append({'role': 'user', 'content': test_message})
        user_history.append({'role': 'assistant', 'content': response})
        active_sessions[clean_phone]['conversation_history'] = user_history
        
        # Create HTML display of restaurants
        html_response += "<p><strong>Available Restaurants:</strong></p><ol>"
        for batch in batches:
            restaurant = batch['restaurant_name']
            location = batch['location']
            current_orders = batch['current_orders']
            max_orders = batch['max_orders']
            fee = batch['delivery_fee']
            
            batch_time = datetime.fromisoformat(str(batch['batch_time'])) if isinstance(batch['batch_time'], str) else batch['batch_time']
            batch_time_str = batch_time.strftime("%I:%M %p")
            
            html_response += f"<li><strong>{restaurant}</strong> ({location}, {batch_time_str}) - ${fee:.2f} delivery fee, {current_orders}/{max_orders} spots filled</li>"
        html_response += "</ol>"
        html_response += "<p>To order, text 'ORDER' followed by what you want. Don't see a restaurant you want? Call (708) 901-1754 to order.</p>"
        html_response += "<p>Text 'PAY' when you're ready to pay.</p>"
    
    elif first_word == 'order':
        # Process a free-form order
        if len(test_message) <= 6:
            html_response += "<p>Please tell us what you'd like to order by texting 'ORDER' followed by your items.</p>"
            html_response += "<p>For example: 'ORDER 2 burritos from Chipotle with extra guac and chips'</p>"
            
            # Update conversation history
            response = "Please tell us what you'd like to order by texting 'ORDER' followed by your items. For example: 'ORDER 2 burritos from Chipotle with guac and chips'"
            user_history.append({'role': 'user', 'content': test_message})
            user_history.append({'role': 'assistant', 'content': response})
            active_sessions[clean_phone]['conversation_history'] = user_history
        else:
            # Extract order text (everything after "order ")
            order_text = test_message[6:].strip()
            
            # Process the order with AI
            ai_response, restaurant_name, batch_info = ai_process_order(order_text, clean_phone)
            
            # Store in active session
            if clean_phone not in active_sessions:
                import datetime as dt
                active_sessions[clean_phone] = {
                    'user_id': user_id,
                    'order_text': order_text,
                    'started_at': dt.datetime.now()
                }
                if restaurant_name:
                    active_sessions[clean_phone]['restaurant'] = restaurant_name
                if batch_info:
                    active_sessions[clean_phone]['batch_info'] = batch_info
            else:
                active_sessions[clean_phone]['order_text'] = order_text
                if restaurant_name:
                    active_sessions[clean_phone]['restaurant'] = restaurant_name
                if batch_info:
                    active_sessions[clean_phone]['batch_info'] = batch_info
            
            # Update conversation history
            user_history.append({'role': 'user', 'content': test_message})
            user_history.append({'role': 'assistant', 'content': ai_response})
            active_sessions[clean_phone]['conversation_history'] = user_history
            
            html_response += f"<p><strong>Order Response:</strong></p>"
            html_response += f"<p>{ai_response}</p>"
            
            # Simulate admin notification
            html_response += "<div style='margin-top: 20px; padding: 10px; background-color: #f8f9fa; border: 1px solid #ddd;'>"
            html_response += "<p><strong>Admin Notification:</strong></p>"
            html_response += f"<p>NEW TEXT ORDER RECEIVED!<br/>Customer: {test_phone}</p>"
            
            if restaurant_name:
                html_response += f"<p>Restaurant: {restaurant_name}</p>"
            html_response += f"<p>Order: {order_text}</p>"
            html_response += "<p>Customer will need to text 'PAY' to receive payment link.</p>"
            html_response += "</div>"
    
    elif first_word == 'pay':
        # Generate a payment link - either real Stripe or simulation
        import datetime as dt
        payment_session_id = f"pay_{clean_phone}_{int(dt.datetime.now().timestamp())}"
        payment_link = ""
        
        # Default delivery fee (now $4)
        delivery_fee = 4.00
        
        # Get delivery fee from batch info if available
        has_active_order = clean_phone in active_sessions
        if has_active_order and 'batch_info' in active_sessions[clean_phone]:
            batch_info = active_sessions[clean_phone]['batch_info']
            if batch_info and 'delivery_fee' in batch_info:
                delivery_fee = float(batch_info['delivery_fee'])
        
        # If Stripe is configured, create a real checkout session for testing
        if stripe_secret_key:
            try:
                # Create a product for the food order
                food_product = stripe.Product.create(
                    name="TreeHouse Food Order",
                    description=f"Your food order + ${delivery_fee:.2f} delivery fee"
                )
                
                # Create a price with custom_unit_amount enabled
                food_price = stripe.Price.create(
                    product=food_product.id,
                    currency="usd",
                    custom_unit_amount={"enabled": True}
                )
                
                # Create a checkout session with the custom amount price
                checkout_session = stripe.checkout.Session.create(
                    payment_method_types=['card'],
                    line_items=[
                        {
                            'price': food_price.id,
                            'quantity': 1
                        }
                    ],
                    mode='payment',
                    success_url=request.base_url + '?result=success&session_id={CHECKOUT_SESSION_ID}',
                    cancel_url=request.base_url + '?result=cancel',
                    metadata={
                        'phone_number': clean_phone,
                        'test': 'true',
                        'user_id': str(user_id),
                        'includes_delivery_fee': 'true'
                    },
                    custom_text={
                        'submit': {'message': 'Pay for order'}
                    }
                )
                
                payment_session_id = checkout_session.id
                payment_link = checkout_session.url
                
                # Create the payment response
                response = "Here's your payment link:\n" + payment_link + "\n\n"
                response += f"Please enter the TOTAL amount including BOTH your food cost AND the ${delivery_fee:.2f} delivery fee.\n"
                response += f"For example, if your food costs $15, enter ${15 + delivery_fee:.2f} total."
                
                if has_active_order:
                    order_text = active_sessions[clean_phone].get('order_text', '')
                    restaurant = active_sessions[clean_phone].get('restaurant', '')
                    response += f"\n\nFor reference, your order was: {order_text}"
                    if restaurant:
                        response += f"\nRestaurant: {restaurant}"
                
                # Update conversation history
                user_history.append({'role': 'user', 'content': test_message})
                user_history.append({'role': 'assistant', 'content': response})
                active_sessions[clean_phone]['conversation_history'] = user_history
                
                html_response += "<p><strong>Real Stripe Checkout Created!</strong></p>"
                html_response += "<p>Please enter the total amount including your food cost plus the $4 delivery fee.</p>"
                html_response += "<p>For example, if your food costs $15, enter $19 total.</p>"
                
            except Exception as e:
                logger.error(f"Error creating test Stripe session: {e}")
                payment_link = f"https://checkout.stripe.com/pay/test_{payment_session_id}"
                html_response += f"<p><strong>Error creating Stripe session:</strong> {str(e)}</p>"
                html_response += "<p>Using simulation instead.</p>"
                
                # Create fallback response
                response = "Here's your payment link:\n" + payment_link + "\n\n"
                response += f"Please enter the total amount including both your food cost AND the ${delivery_fee:.2f} delivery fee."
                
                if has_active_order:
                    order_text = active_sessions[clean_phone].get('order_text', '')
                    response += f"\n\nFor reference, your order was: {order_text}"
                
                # Update conversation history
                user_history.append({'role': 'user', 'content': test_message})
                user_history.append({'role': 'assistant', 'content': response})
                active_sessions[clean_phone]['conversation_history'] = user_history
        else:
            # Use a simulation
            payment_link = f"https://checkout.stripe.com/pay/test_{payment_session_id}"
            html_response += "<p>Stripe not configured. Using simulation.</p>"
            
            # Create fallback response
            response = "Here's your payment link:\n" + payment_link + "\n\n"
            response += f"Please enter the total amount including both your food cost AND the ${delivery_fee:.2f} delivery fee."
            
            if has_active_order:
                order_text = active_sessions[clean_phone].get('order_text', '')
                response += f"\n\nFor reference, your order was: {order_text}"
            
            # Update conversation history
            user_history.append({'role': 'user', 'content': test_message})
            user_history.append({'role': 'assistant', 'content': response})
            active_sessions[clean_phone]['conversation_history'] = user_history
        
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
        html_response += "<p>Please enter the total amount including both your food cost AND the $4 delivery fee.</p>"
        
        # If Stripe is not configured, show a visual simulation
        if not stripe_secret_key:
            html_response += """
            <div id="stripeSimulator" style="margin-top:20px; padding:20px; border:1px solid #ccc; border-radius:8px; background-color:#f8f9fa;">
                <h3 style="margin-top:0;">Stripe Checkout Simulation</h3>
                <div style="background-color:#fff; border:1px solid #eee; border-radius:4px; padding:15px; margin-bottom:15px;">
                    <div style="margin-bottom:10px; font-weight:bold;">TreeHouse Food Delivery</div>
                    <div style="display:flex; justify-content:space-between; margin-bottom:15px;">
                        <div>Total Amount (Food + $4 Delivery)</div>
                        <div><input type="number" id="totalAmount" min="5" step="0.01" value="19.00" style="width:70px; text-align:right;"></div>
                    </div>
                </div>
                <button onclick="simulatePayment()" style="background-color:#5469d4; color:white; border:none; padding:10px 15px; border-radius:4px; cursor:pointer;">Pay</button>
            </div>
            
            <script>
            function simulatePayment() {
                const total = parseFloat(document.getElementById('totalAmount').value);
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
        
        # Create payment confirmation response
        batch_time_str = "upcoming batch"
        if clean_phone in active_sessions and 'batch_info' in active_sessions[clean_phone]:
            batch_info = active_sessions[clean_phone]['batch_info']
            if batch_info and 'batch_time' in batch_info:
                batch_time = batch_info['batch_time']
                batch_time_str = datetime.fromisoformat(str(batch_time)).strftime("%I:%M %p") if isinstance(batch_time, str) else batch_time.strftime("%I:%M %p")
        
        restaurant = "your restaurant"
        batch_location = "your location"
        if clean_phone in active_sessions:
            restaurant = active_sessions[clean_phone].get('restaurant', 'your restaurant')
            if 'batch_info' in active_sessions[clean_phone]:
                batch_info = active_sessions[clean_phone]['batch_info']
                if batch_info and 'location' in batch_info:
                    batch_location = batch_info['location']
        
        # Create simulated confirmation message
        ai_response = f"""Payment confirmed! Your {restaurant} order is set for pickup at {batch_location} between {batch_time_str}-{batch_time_str[:-3]}:03{batch_time_str[-3:]}.

Your batch is currently 5/10 full.

We'll text you when the batch is locked in.

Reply "CANCEL" within the next 10 minutes if you need to cancel."""
        
        # Add to conversation history
        user_history.append({'role': 'assistant', 'content': ai_response})
        active_sessions[clean_phone]['conversation_history'] = user_history
        
        success_html = f"""
        <div style="margin-top: 20px; padding: 20px; background-color: #d4edda; border-radius: 8px; text-align: center;">
            <h3 style="color: #155724; margin-top:0;">Payment Successful!</h3>
            <p>Your order has been processed. You would receive a text confirmation shortly.</p>
            <p>Session ID: {session_id}</p>
            <p>{'(Simulated payment)' if simulation == 'true' else ''}</p>
        </div>
        
        <div style="margin-top: 20px; padding: 15px; background-color: #e9f7ef; border: 1px solid #ddd; border-radius: 8px;">
            <p><strong>Payment Confirmation Message:</strong></p>
            <p style="white-space: pre-line;">{ai_response}</p>
        </div>
        """
        html_response += success_html
        
        # Simulate batch confirmation after 30 seconds (in real system)
        if has_active_order:
            batch_confirm = f"""Your {restaurant} batch is locked in!

5 orders total. Delivery to {batch_location} at {batch_time_str}.

Your pickup window: {batch_time_str}-{batch_time_str[:-3]}:03{batch_time_str[-3:]}"""
            
            html_response += f"""
            <div style="margin-top: 20px; padding: 15px; background-color: #f0f5ff; border: 1px solid #cce5ff; border-radius: 8px;">
                <p><strong>30 Seconds Later - Batch Confirmation Message:</strong></p>
                <p style="white-space: pre-line;">{batch_confirm}</p>
                <p><em>(In the real system, this would be sent when the batch is confirmed)</em></p>
            </div>
            """
            
            # Add follow-up message
            follow_up = """Thanks for using TreeHouse! Hope you enjoyed your meal.

Next batch opens at 1:25 PM. Text anything to see options!"""
            
            html_response += f"""
            <div style="margin-top: 20px; padding: 15px; background-color: #fff5e6; border: 1px solid #ffe0b2; border-radius: 8px;">
                <p><strong>After Delivery - Follow-up Message:</strong></p>
                <p style="white-space: pre-line;">{follow_up}</p>
                <p><em>(In the real system, this would be sent after the scheduled pickup time)</em></p>
            </div>
            """
    elif result == 'cancel':
        cancel_html = """
        <div style="margin-top: 20px; padding: 20px; background-color: #f8d7da; border-radius: 8px; text-align: center;">
            <h3 style="color: #721c24; margin-top:0;">Payment Cancelled</h3>
            <p>Your payment was cancelled. You would need to text PAY again to get a new payment link.</p>
        </div>
        """
        html_response += cancel_html
    
    elif first_word in ['help', 'info']:
        # Create help response
        response = "TreeHouse - Restaurant delivery for ONLY $4!\n\n"
        response += "Commands:\n"
        response += "• Text 'MENU' to see available restaurants\n"
        response += "• Text 'ORDER' followed by what you want (e.g., 'ORDER 2 burritos from Chipotle')\n"
        response += "• Text 'PAY' to get a payment link\n"
        response += "• Call (708) 901-1754 for special orders or questions\n\n"
        response += "Food is delivered hourly. Order by :25-:30 of each hour to get your food at the top of the next hour."
        
        # Update conversation history
        user_history.append({'role': 'user', 'content': test_message})
        user_history.append({'role': 'assistant', 'content': response})
        active_sessions[clean_phone]['conversation_history'] = user_history
        
        html_response += "<p><strong>TreeHouse Help</strong></p>"
        html_response += "<ul>"
        html_response += "<li>Text 'MENU' to see available restaurants</li>"
        html_response += "<li>Text 'ORDER' followed by what you want</li>"
        html_response += "<li>Text 'PAY' to get a payment link</li>"
        html_response += "<li>Call (708) 901-1754 for special orders or questions</li>"
        html_response += "</ul>"
        html_response += "<p>Food is delivered hourly. Order by :25-:30 of each hour to get your food at the top of the next hour.</p>"
    
    else:
        # Process general message with AI
        # Check if OpenAI API is available
        if openai_api_key:
            # Use appropriate system instructions for the TreeHouse assistant
            system_prompt = """
            You are the TreeHouse food delivery assistant. You help users order food from nearby restaurants with low delivery fees.
            
            These are the main commands:
            - MENU: Show available restaurants
            - ORDER [food details]: Place an order
            - PAY: Get a payment link
            
            When responding to users, be helpful, friendly, and concise. If you can't answer a specific question,
            suggest texting 'MENU' to see restaurant options or 'ORDER' followed by what they want.
            
            Remember that TreeHouse offers $4 delivery from select restaurants, much lower than other delivery services.
            Orders are delivered hourly - users need to order by :25-:30 of each hour to get food at the top of the next hour.
            
            If users share TreeHouse with friends, they can get free items like chips, cookies, or drinks.
            """
            
            # Prepare messages for the API call
            messages = [
                {"role": "system", "content": system_prompt}
            ]
            
            # Add conversation history
            if len(user_history) > 0:
                for entry in user_history[-6:]:  # Last 6 messages (3 exchanges)
                    messages.append({
                        "role": entry["role"],
                        "content": entry["content"]
                    })
            
            # Add the current message
            messages.append({"role": "user", "content": test_message})
            
            try:
                # Call OpenAI API
                # Call OpenAI API
                client = openai.OpenAI(api_key=openai_api_key)
                ai_response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=messages,
                    max_tokens=300,
                    temperature=0.7
                )
                
                # Extract the AI response
                response = ai_response.choices[0].message.content
                
                # Add a suggestion to use the primary commands if not mentioned
                if not any(keyword in response.lower() for keyword in ['menu', 'order', 'pay']):
                    response += "\n\nText 'MENU' to see restaurant options or 'ORDER' followed by what you want."
                
                # Update conversation history
                user_history.append({'role': 'user', 'content': test_message})
                user_history.append({'role': 'assistant', 'content': response})
                active_sessions[clean_phone]['conversation_history'] = user_history
                
                html_response += "<p><strong>AI-Powered Response:</strong></p>"
                html_response += f"<p style='white-space: pre-line;'>{response}</p>"
                html_response += "<p><em>(Response generated by OpenAI's model)</em></p>"
                
            except Exception as e:
                logger.error(f"Error using OpenAI for conversation: {e}")
                response = "I didn't understand that command. Text 'MENU' to see restaurants, 'ORDER' followed by what you want, or 'PAY' to get a payment link. Need help? Text 'HELP' or call (708) 901-1754."
                
                # Update conversation history
                user_history.append({'role': 'user', 'content': test_message})
                user_history.append({'role': 'assistant', 'content': response})
                active_sessions[clean_phone]['conversation_history'] = user_history
                
                html_response += "<p><strong>Fallback Response (OpenAI Error):</strong></p>"
                html_response += f"<p>{response}</p>"
                html_response += f"<p><em>Error: {str(e)}</em></p>"
        else:
            # Fallback response without AI
            response = "I didn't understand that command. Text 'MENU' to see restaurants, 'ORDER' followed by what you want, or 'PAY' to get a payment link. Need help? Text 'HELP' or call (708) 901-1754."
            
            # Update conversation history
            user_history.append({'role': 'user', 'content': test_message})
            user_history.append({'role': 'assistant', 'content': response})
            active_sessions[clean_phone]['conversation_history'] = user_history
            
            html_response += "<p><strong>Standard Response:</strong></p>"
            html_response += f"<p>{response}</p>"
            html_response += "<p><em>(OpenAI not configured - using standard response)</em></p>"
    
    # Display active session if it exists
    if clean_phone in active_sessions:
        session_info = active_sessions[clean_phone]
        html_response += "<div style='margin-top: 20px; padding: 10px; background-color: #e9f7ef; border: 1px solid #ddd;'>"
        html_response += "<p><strong>Current Session Info:</strong></p>"
        
        # Show only non-sensitive, non-history keys
        safe_session = {k: v for k, v in session_info.items() if k != 'conversation_history'}
        html_response += "<table style='width: 100%; border-collapse: collapse;'>"
        for key, value in safe_session.items():
            if key == 'started_at':  # Format datetime
                if isinstance(value, datetime):
                    value = value.strftime("%Y-%m-%d %H:%M:%S")
            elif key == 'batch_info' and isinstance(value, dict):  # Format batch dict
                value = "<pre>" + str({k: (v.strftime("%Y-%m-%d %H:%M:%S") if k == 'batch_time' and isinstance(v, datetime) else v) for k, v in value.items()}) + "</pre>"
            elif key == 'batch_time' and isinstance(value, datetime):  # Format datetime
                value = value.strftime("%Y-%m-%d %H:%M:%S")
                
            html_response += f"<tr><td style='padding: 5px; border: 1px solid #ddd; font-weight: bold;'>{key}</td><td style='padding: 5px; border: 1px solid #ddd;'>{value}</td></tr>"
        html_response += "</table>"
        
        # Add conversation history with short preview
        if 'conversation_history' in session_info and session_info['conversation_history']:
            html_response += "<p><strong>Conversation Preview:</strong></p>"
            html_response += "<div style='max-height: 150px; overflow-y: auto; border: 1px solid #ddd; padding: 5px;'>"
            for i, entry in enumerate(session_info['conversation_history'][-4:]):  # Show last 4 entries
                role = entry['role']
                content = entry['content'][:50] + "..." if len(entry['content']) > 50 else entry['content']
                html_response += f"<p><strong>{role.title()}:</strong> {content}</p>"
            html_response += "</div>"
        
        html_response += "</div>"
    
    conn.close()
    
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
                    <li><code>cancel</code> - Cancel your current order (within 10 minutes)</li>
                    <li>Try asking a general question - AI will respond if configured</li>
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
                if twilio_client:
                    try:
                        # Get batch information if available
                        batch_time_str = "upcoming batch"
                        restaurant = "your order"
                        batch_location = "your location"
                        
                        if phone_number in active_sessions:
                            phone_session = active_sessions[phone_number]
                            restaurant = phone_session.get('restaurant', 'your order')
                            
                            if 'batch_info' in phone_session:
                                batch_info = phone_session['batch_info']
                                
                                if batch_info and 'batch_time' in batch_info:
                                    batch_time = batch_info['batch_time']
                                    batch_time_str = datetime.fromisoformat(str(batch_time)).strftime("%I:%M %p") if isinstance(batch_time, str) else batch_time.strftime("%I:%M %p")
                                
                                if batch_info and 'location' in batch_info:
                                    batch_location = batch_info['location']
                        
                        # Create confirmation message
                        confirmation = f"""Payment confirmed! Your {restaurant} order is set for pickup at {batch_location} between {batch_time_str}-{batch_time_str[:-3]}:03{batch_time_str[-3:]}.

Your batch is currently 5/10 full.

We'll text you when the batch is locked in.

Reply "CANCEL" within the next 10 minutes if you need to cancel."""
                        
                        message = twilio_client.messages.create(
                            body=confirmation,
                            from_=twilio_phone,
                            to=f"+{phone_number}"
                        )
                        logger.info(f"Payment confirmation sent to +{phone_number}")
                        
                        # Also simulate the "batch locked in" message after 30 seconds
                        import threading
                        def send_batch_confirmation():
                            time.sleep(30)  # Wait 30 seconds
                            try:
                                batch_confirm = f"""Your {restaurant} batch is locked in!

5 orders total. Delivery to {batch_location} at {batch_time_str}.

Your pickup window: {batch_time_str}-{batch_time_str[:-3]}:03{batch_time_str[-3:]}"""
                                
                                twilio_client.messages.create(
                                    body=batch_confirm,
                                    from_=twilio_phone,
                                    to=f"+{phone_number}"
                                )
                                logger.info(f"Batch confirmation sent to +{phone_number}")
                            except Exception as e:
                                logger.error(f"Error sending batch confirmation: {e}")
                        
                        # Start the timer thread
                        timer_thread = threading.Thread(target=send_batch_confirmation)
                        timer_thread.daemon = True
                        timer_thread.start()
                        
                    except Exception as e:
                        logger.error(f"Error sending payment confirmation: {e}")
                
                # Notify admin about payment
                if twilio_client:
                    try:
                        # Get order details if available
                        order_details = ""
                        if phone_number in active_sessions:
                            order_text = active_sessions[phone_number].get('order_text', '')
                            restaurant = active_sessions[phone_number].get('restaurant', '')
                            
                            if order_text:
                                order_details = f"\nOrder: {order_text}"
                            
                            if restaurant:
                                order_details += f"\nRestaurant: {restaurant}"
                        
                        twilio_client.messages.create(
                            body=f"Payment received! Phone: +{phone_number}, Amount: ${payment_amount:.2f}, Stripe ID: {payment_id}{order_details}",
                            from_=twilio_phone,
                            to=notification_email
                        )
                        logger.info(f"Admin payment notification sent")
                    except Exception as e:
                        logger.error(f"Error sending admin payment notification: {e}")
                
            except Exception as e:
                logger.error(f"Error recording payment: {e}")
    
    return jsonify({"status": "success"}), 200


@app.route('/privacy-policy.html')
def serve_privacy_policy_simple():
    try:
        # Try looking in multiple possible locations
        locations = [
            'static/react/privacy-policy.html',         # Standard location
            'backend/static/react/privacy-policy.html', # Full path from root
            'static/react/static/privacy-policy.html',  # Nested static folder
            'privacy-policy.html'                       # Root directory
        ]
        
        for location in locations:
            if os.path.exists(location):
                # Return the first one that exists
                directory, filename = os.path.split(location)
                return send_from_directory(directory or '.', filename)
        
        # If none found, return a helpful error with more debugging info
        all_static_files = []
        for root, dirs, files in os.walk('static'):
            for file in files:
                all_static_files.append(os.path.join(root, file))
                
        return jsonify({
            "error": "Privacy policy not found",
            "working_directory": os.getcwd(),
            "checked_locations": locations,
            "all_static_files": all_static_files[:20]  # Limit to first 20 files
        }), 404
    except Exception as e:
        return f"Error: {str(e)}", 500

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
    # Start the scheduler
    start_scheduler()
    
    # Run the Flask app
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=True)
