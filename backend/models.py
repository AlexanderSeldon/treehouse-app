from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

# These model classes mirror your existing SQLite tables
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    phone_number = db.Column(db.String(15), unique=True, nullable=False)
    name = db.Column(db.String(100))
    email = db.Column(db.String(100))
    dorm_building = db.Column(db.String(100))
    room_number = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    orders = db.relationship('Order', backref='user', lazy=True)

class Menu(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    restaurant_name = db.Column(db.String(100), nullable=False)
    menu_path = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    menu_items = db.relationship('MenuItem', backref='menu', lazy=True)

class MenuItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    menu_id = db.Column(db.Integer, db.ForeignKey('menu.id'), nullable=False)
    item_name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50))
    image_path = db.Column(db.String(255))
    is_available = db.Column(db.Boolean, default=True)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    delivery_fee = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')
    scheduled_delivery_time = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    items = db.relationship('OrderItem', backref='order', lazy=True)

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    menu_item_id = db.Column(db.Integer, db.ForeignKey('menu_item.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    item_price = db.Column(db.Float, nullable=False)
    special_instructions = db.Column(db.Text)
    menu_item = db.relationship('MenuItem')

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(50), nullable=False)
    transaction_id = db.Column(db.String(100))
    status = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class DeliveryBatch(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    delivery_time = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='scheduled')
    driver_name = db.Column(db.String(100))
    driver_phone = db.Column(db.String(15))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    orders = db.relationship('Order', secondary='batch_orders')

# This represents your batch_orders join table
batch_orders = db.Table('batch_orders',
    db.Column('batch_id', db.Integer, db.ForeignKey('delivery_batch.id'), primary_key=True),
    db.Column('order_id', db.Integer, db.ForeignKey('order.id'), primary_key=True)
)
