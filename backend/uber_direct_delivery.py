import requests
import json
import time
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class UberDirectDelivery:
    def __init__(self, client_id: str, client_secret: str, customer_id: str, test_mode: bool = True):
        """
        Initialize Uber Direct delivery service
        
        Args:
            client_id: Uber Direct API client ID
            client_secret: Uber Direct API client secret
            customer_id: Uber Direct customer ID
            test_mode: Whether to use test mode with robo couriers
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.customer_id = customer_id
        self.test_mode = test_mode
        self.access_token = None
        self.token_expiry = None
        
        # Single campus drop-off location - Richard J Daley Library
        self.campus_buildings = {
            "Library": {
                "address": "801 S Morgan St, Chicago, IL 60607",
                "latitude": 41.8718,  # Approximate coordinates
                "longitude": -87.6498,
                "phone": "+13129962724"  # Library phone number
            }
        }
        
        # Restaurant locations with actual addresses
        self.restaurant_locations = {
            "Chipotle": {
                "address": "1132 S Clinton St, Chicago, IL 60607",
                "latitude": 41.8678,  # Approximate coordinates
                "longitude": -87.6410,
                "phone": "+13122434300"  # You may want to update with actual phone
            },
            "McDonald's": {
                "address": "2315 W Ogden Ave, Chicago, IL 60608",
                "latitude": 41.8630,  # Approximate coordinates
                "longitude": -87.6861,
                "phone": "+17734550650"  # You may want to update with actual phone
            },
            "Chick-fil-A": {
                "address": "1106 S Clinton St, Chicago, IL 60607",
                "latitude": 41.8679,  # Approximate coordinates
                "longitude": -87.6410,
                "phone": "+13124619110"  # You may want to update with actual phone
            },
            "Portillo's": {
                "address": "520 W Taylor St, Chicago, IL 60607",
                "latitude": 41.8697,  # Approximate coordinates
                "longitude": -87.6407,
                "phone": "+13128772300"  # You may want to update with actual phone
            },
            "Starbucks": {
                "address": "1430 W Taylor St, Chicago, IL 60607",
                "latitude": 41.8692,  # Approximate coordinates
                "longitude": -87.6629,
                "phone": "+13122267773"  # You may want to update with actual phone
            }
        }
    
    def get_access_token(self) -> str:
        """
        Get OAuth token from Uber Direct API
        
        Returns:
            str: Access token
        """
        # Check if token is still valid
        current_time = time.time()
        if self.access_token and self.token_expiry and current_time < self.token_expiry:
            logger.info("Using existing access token")
            return self.access_token
        
        try:
            url = 'https://auth.uber.com/oauth/v2/token'
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            payload = {
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'grant_type': 'client_credentials',
                'scope': 'eats.deliveries'
            }
            
            response = requests.post(url, headers=headers, data=payload)
            response.raise_for_status()
            
            token_data = response.json()
            self.access_token = token_data['access_token']
            # Set expiry to 10 minutes before actual expiry to be safe
            self.token_expiry = current_time + token_data.get('expires_in', 3600) - 600
            
            logger.info("Access token obtained successfully")
            return self.access_token
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting access token: {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response: {e.response.text}")
            raise
    
    def format_address(self, address: str) -> str:
        """
        Format address for Uber Direct API
        
        Args:
            address: Address string
            
        Returns:
            str: JSON string of formatted address
        """
        parts = address.split(',')
        
        # Extract zip code from the last part of the address
        zip_parts = parts[-1].strip().split(' ')
        zip_code = zip_parts[-1] if len(zip_parts) > 1 else "60607"  # Default if no zip found
        
        # Create address object
        address_obj = {
            "street_address": [parts[0].strip()],
            "city": "Chicago",
            "state": "IL",
            "zip_code": zip_code,
            "country": "US"
        }
        
        return json.dumps(address_obj)
    
    def get_delivery_windows(self, batch_time: datetime) -> Dict[str, str]:
        """
        Calculate delivery windows based on batch time
        
        Args:
            batch_time: The batch time from the database
            
        Returns:
            dict: Dictionary with pickup and dropoff window timestamps
        """
        now = datetime.now()
        
        # If batch time is in the past, use current time as base
        base_time = max(now, batch_time)
        
        # For ASAP delivery (if batch time is recent)
        if (base_time - now).total_seconds() < 900:  # Within 15 minutes
            # No need to set delivery windows for ASAP delivery
            return {}
        
        # For scheduled delivery
        # Calculate windows
        # We want couriers to arrive 15 minutes after batch closes
        pickup_ready = base_time + timedelta(minutes=15)
        # Allow 30 minute window for pickup
        pickup_deadline = pickup_ready + timedelta(minutes=30)
        # Dropoff can start as soon as pickup is complete
        dropoff_ready = pickup_deadline
        # Allow 60 minute window for dropoff
        dropoff_deadline = dropoff_ready + timedelta(minutes=60)
        
        # Format as ISO strings
        return {
            "pickup_ready_dt": pickup_ready.isoformat() + "Z",
            "pickup_deadline_dt": pickup_deadline.isoformat() + "Z",
            "dropoff_ready_dt": dropoff_ready.isoformat() + "Z",
            "dropoff_deadline_dt": dropoff_deadline.isoformat() + "Z"
        }
    
    def create_quote(self, restaurant_name: str, destination_name: str, delivery_windows: Dict[str, str] = None) -> Dict[str, Any]:
        """
        Create a delivery quote for a restaurant to a destination
        
        Args:
            restaurant_name: Name of the restaurant
            destination_name: Name of the campus building for delivery
            delivery_windows: Optional dictionary with delivery window timestamps
            
        Returns:
            dict: Quote data
        """
        token = self.get_access_token()
        
        try:
            url = f"https://api.uber.com/v1/customers/{self.customer_id}/delivery_quotes"
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {token}'
            }
            
            restaurant = self.restaurant_locations.get(restaurant_name)
            destination = self.campus_buildings.get(destination_name)
            
            if not restaurant:
                raise ValueError(f"Restaurant '{restaurant_name}' not found")
            if not destination:
                raise ValueError(f"Destination '{destination_name}' not found")
            
            payload = {
                "pickup_address": self.format_address(restaurant["address"]),
                "dropoff_address": self.format_address(destination["address"]),
                "pickup_latitude": restaurant["latitude"],
                "pickup_longitude": restaurant["longitude"],
                "dropoff_latitude": destination["latitude"],
                "dropoff_longitude": destination["longitude"]
            }
            
            # Add delivery windows if provided
            if delivery_windows:
                for key, value in delivery_windows.items():
                    if value:
                        payload[key] = value
            
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            quote_data = response.json()
            
            # Display quote info
            logger.info(f"Quote created for {restaurant_name} to {destination_name}:")
            logger.info(f"Quote ID: {quote_data['id']}")
            logger.info(f"Price: ${quote_data['fee']/100:.2f} {quote_data['currency']}")
            
            if 'pickup_duration' in quote_data:
                logger.info(f"Estimated pickup time: {quote_data['pickup_duration']} minutes")
            
            if 'dropoff_eta' in quote_data:
                dropoff_time = datetime.fromisoformat(quote_data['dropoff_eta'].replace('Z', '+00:00'))
                logger.info(f"Estimated dropoff time: {dropoff_time.strftime('%I:%M:%S %p')}")
            
            return quote_data
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Error creating quote for {restaurant_name}: {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response: {e.response.text}")
            raise
    
    def create_delivery(self, restaurant_name: str, destination_name: str, 
                        orders: List[Dict[str, Any]], quote: Dict[str, Any],
                        delivery_windows: Dict[str, str] = None) -> Dict[str, Any]:
        """
        Create a delivery for a restaurant with consolidated orders
        
        Args:
            restaurant_name: Name of the restaurant
            destination_name: Name of the campus building for delivery
            orders: List of orders with customer name and items
            quote: Quote data from create_quote
            delivery_windows: Optional dictionary with delivery window timestamps
            
        Returns:
            dict: Delivery data
        """
        token = self.get_access_token()
        
        try:
            restaurant = self.restaurant_locations.get(restaurant_name)
            destination = self.campus_buildings.get(destination_name)
            
            if not restaurant:
                raise ValueError(f"Restaurant '{restaurant_name}' not found")
            if not destination:
                raise ValueError(f"Destination '{destination_name}' not found")
            
            # Consolidate orders into a manifest
            manifest_items = []
            
            for order in orders:
                customer_name = order.get("customer_name", "Unknown")
                order_number = order.get("order_number", "")
                
                # Create item identifier based on order number and customer name
                item_identifier = f"#{order_number} " if order_number else ""
                item_identifier += f"for {customer_name}"
                
                # Add the order as a single manifest item
                manifest_items.append({
                    "name": f"Order {item_identifier}",
                    "quantity": 1,
                    "weight": 500,  # Approximate weight in grams
                    "dimensions": {
                        "length": 25,
                        "height": 15,
                        "depth": 20
                    }
                })
            
            url = f"https://api.uber.com/v1/customers/{self.customer_id}/deliveries"
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {token}'
            }
            
            payload = {
                "quote_id": quote["id"],
                "pickup_address": self.format_address(restaurant["address"]),
                "pickup_name": restaurant_name,
                "pickup_phone_number": restaurant["phone"],
                "pickup_latitude": restaurant["latitude"],
                "pickup_longitude": restaurant["longitude"],
                "dropoff_address": self.format_address(destination["address"]),
                "dropoff_name": destination_name,
                "dropoff_phone_number": destination["phone"],
                "dropoff_latitude": destination["latitude"],
                "dropoff_longitude": destination["longitude"],
                "manifest_items": manifest_items,
                "external_id": f"{restaurant_name.replace(' ', '-').lower()}-batch-{datetime.now().strftime('%Y%m%d%H%M')}",
            }
            
            # Add delivery windows if provided
            if delivery_windows:
                for key, value in delivery_windows.items():
                    if value:
                        payload[key] = value
            
            # Add Robo Courier for testing if in test mode
            if self.test_mode:
                payload["test_specifications"] = {
                    "robo_courier_specification": {
                        "mode": "auto"
                    }
                }
            
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            delivery_data = response.json()
            
            # Display delivery info
            logger.info(f"Delivery created with ID: {delivery_data['id']}")
            logger.info(f"Status: {delivery_data['status']}")
            
            if 'tracking_url' in delivery_data:
                logger.info(f"Tracking URL: {delivery_data['tracking_url']}")
            
            return delivery_data
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Error creating delivery for {restaurant_name}: {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response: {e.response.text}")
            raise
    
    def process_batch(self, batch_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """
        Process a batch of orders grouped by restaurant
        
        Args:
            batch_data: Dictionary with campus location and orders by restaurant
            
        Returns:
            dict: Dictionary of delivery data by restaurant
        """
        deliveries = {}
        
        # Always use the Library as the destination
        destination_name = "Library"
        restaurants_orders = batch_data.get("restaurants", {})
        
        # Get batch time for delivery windows
        batch_time = batch_data.get("batch_time")
        delivery_windows = None
        
        # Calculate delivery windows if batch time is available
        if batch_time:
            if isinstance(batch_time, str):
                # Convert string to datetime if needed
                batch_time = datetime.fromisoformat(batch_time.replace('Z', '+00:00'))
            
            delivery_windows = self.get_delivery_windows(batch_time)
            logger.info(f"Using delivery windows: {delivery_windows}")
        
        for restaurant_name, orders in restaurants_orders.items():
            if not orders:
                logger.info(f"Skipping {restaurant_name} - no orders")
                continue
                
            logger.info(f"\n========= Processing {restaurant_name} =========")
            logger.info(f"Consolidating {len(orders)} orders for delivery to {destination_name}")
            
            try:
                # Create quote
                quote = self.create_quote(restaurant_name, destination_name, delivery_windows)
                
                # Create delivery with the quote
                delivery = self.create_delivery(restaurant_name, destination_name, orders, quote, delivery_windows)
                
                # Store the delivery data
                deliveries[restaurant_name] = {
                    "quote": quote,
                    "delivery": delivery,
                    "orders": orders,
                    "destination": destination_name
                }
                
                # Wait to avoid rate limits
                time.sleep(1)
            except Exception as e:
                logger.error(f"Error processing {restaurant_name}: {e}")
        
        logger.info("\n========= All deliveries have been processed! =========")
        return deliveries


def prepare_batch_for_delivery(batch_id: int, database_connection) -> Dict[str, Any]:
    """
    Prepare batch data for delivery from database
    
    Args:
        batch_id: ID of the batch to process
        database_connection: SQLite database connection
        
    Returns:
        dict: Prepared batch data
    """
    cursor = database_connection.cursor()
    
    # Get batch information
    cursor.execute("""
        SELECT db.id, db.delivery_time, db.status, db.driver_name, db.driver_phone
        FROM delivery_batches db
        WHERE db.id = ?
    """, (batch_id,))
    
    batch = cursor.fetchone()
    if not batch:
        raise ValueError(f"Batch with ID {batch_id} not found")
    
    # Get batch time for delivery windows
    batch_time = batch[1]  # delivery_time field
    
    # Get all orders in this batch
    cursor.execute("""
        SELECT o.id, o.user_id, u.name as customer_name, u.dorm_building, u.room_number, 
               o.status, m.restaurant_name
        FROM orders o
        JOIN batch_orders bo ON o.id = bo.order_id
        JOIN users u ON o.user_id = u.id
        JOIN order_items oi ON o.id = oi.order_id
        JOIN menu_items mi ON oi.menu_item_id = mi.id
        JOIN menus m ON mi.menu_id = m.id
        WHERE bo.batch_id = ?
        GROUP BY o.id
    """, (batch_id,))
    
    orders = cursor.fetchall()
    
    # Organize orders by restaurant
    restaurants = {}
    
    for order in orders:
        order_id = order[0]
        customer_name = order[2]
        restaurant_name = order[6]
        
        # Get order items
        cursor.execute("""
            SELECT oi.id, oi.quantity, mi.item_name, oi.special_instructions,
                   u.phone_number, p.transaction_id as order_number
            FROM order_items oi
            JOIN menu_items mi ON oi.menu_item_id = mi.id
            JOIN orders o ON oi.order_id = o.id
            JOIN users u ON o.user_id = u.id
            LEFT JOIN payments p ON o.id = p.order_id
            WHERE oi.order_id = ?
        """, (order_id,))
        
        items = cursor.fetchall()
        
        # Get order number from transaction ID or use ID
        order_number = items[0][5] if items and items[0][5] else f"TH-{order_id}"
        
        # Add to restaurants dictionary
        if restaurant_name not in restaurants:
            restaurants[restaurant_name] = []
        
        order_items = []
        for item in items:
            quantity = item[1]
            item_name = item[2]
            special_instructions = item[3]
            
            order_items.append({
                "name": item_name,
                "quantity": quantity,
                "special": special_instructions
            })
        
        restaurants[restaurant_name].append({
            "order_id": order_id,
            "customer_name": customer_name,
            "order_number": order_number,
            "items": order_items
        })
    
    # Always use Library for drop-off
    return {
        "batch_id": batch_id,
        "batch_time": batch_time,  # Include batch time for delivery windows
        "location": "Library",  # Fixed to Library for all batches
        "restaurants": restaurants
    }
