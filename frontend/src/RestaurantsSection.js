import React, { useState, useEffect } from 'react';

const RestaurantsSection = () => {
  const [restaurants, setRestaurants] = useState([]);
  const [selectedRestaurant, setSelectedRestaurant] = useState(null);
  const [menuItems, setMenuItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  // Fetch restaurants on component mount
  useEffect(() => {
    const fetchRestaurants = async () => {
      setLoading(true);
      try {
        const response = await fetch('http://localhost:5001/api/menus');
        if (!response.ok) {
          throw new Error('Failed to fetch restaurants');
        }
        const data = await response.json();
        setRestaurants(data.menus || []);
      } catch (error) {
        setError(error.message);
        console.error('Error fetching restaurants:', error);
      } finally {
        setLoading(false);
      }
    };
    
    fetchRestaurants();
  }, []);
  
  // Fetch menu items when a restaurant is selected
  useEffect(() => {
    if (!selectedRestaurant) return;
    
    const fetchMenuItems = async () => {
      setLoading(true);
      try {
        const response = await fetch(`http://localhost:5001/api/menu-items?restaurant_id=${selectedRestaurant.id}`);
        if (!response.ok) {
          throw new Error('Failed to fetch menu items');
        }
        const data = await response.json();
        setMenuItems(data.menu_items || []);
      } catch (error) {
        setError(error.message);
        console.error('Error fetching menu items:', error);
      } finally {
        setLoading(false);
      }
    };
    
    fetchMenuItems();
  }, [selectedRestaurant]);
  
  const handleRestaurantClick = (restaurant) => {
    setSelectedRestaurant(restaurant);
  };
  
  const handleBack = () => {
    setSelectedRestaurant(null);
    setMenuItems([]);
  };
  
  // Group menu items by category
  const menuByCategory = menuItems.reduce((acc, item) => {
    const category = item.category || 'Other';
    if (!acc[category]) {
      acc[category] = [];
    }
    acc[category].push(item);
    return acc;
  }, {});
  
  if (loading && !restaurants.length) {
    return <div style={{ textAlign: 'center', padding: '40px' }}>Loading...</div>;
  }
  
  if (error && !restaurants.length) {
    return <div style={{ textAlign: 'center', padding: '40px', color: 'red' }}>Error: {error}</div>;
  }
  
  return (
    <section style={{ marginBottom: '50px' }}>
      <h2 style={{ fontSize: '28px', textAlign: 'center', marginBottom: '30px' }}>
        {selectedRestaurant ? `${selectedRestaurant.restaurant_name} Menu` : 'Available Restaurants'}
      </h2>
      
      {selectedRestaurant ? (
        <div>
          <button 
            onClick={handleBack}
            style={{ 
              background: 'transparent', 
              border: '1px solid #1B4332', 
              color: '#1B4332', 
              padding: '8px 16px', 
              borderRadius: '4px', 
              cursor: 'pointer',
              marginBottom: '20px'
            }}
          >
            ← Back to Restaurants
          </button>
          
          <a 
            href={`http://localhost:5001${selectedRestaurant.menu_path}`} 
            target="_blank" 
            rel="noopener noreferrer"
            style={{
              display: 'inline-block',
              background: '#1B4332',
              color: 'white',
              padding: '8px 16px',
              borderRadius: '4px',
              textDecoration: 'none',
              marginBottom: '30px'
            }}
          >
            View Full Menu PDF
          </a>
          
          {loading ? (
            <div style={{ textAlign: 'center', padding: '40px' }}>Loading menu items...</div>
          ) : (
            <div>
              {Object.entries(menuByCategory).map(([category, items]) => (
                <div key={category} style={{ marginBottom: '30px' }}>
                  <h3 style={{ fontSize: '22px', color: '#1B4332', marginBottom: '15px', borderBottom: '1px solid #eee', paddingBottom: '8px' }}>
                    {category}
                  </h3>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '20px' }}>
                    {items.map(item => (
                      <div key={item.id} style={{ border: '1px solid #eee', borderRadius: '8px', padding: '15px', boxShadow: '0 2px 4px rgba(0,0,0,0.05)' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                          <h4 style={{ fontSize: '18px', margin: 0 }}>{item.item_name}</h4>
                          <span style={{ fontWeight: 'bold' }}>${parseFloat(item.price).toFixed(2)}</span>
                        </div>
                        <p style={{ color: '#666', fontSize: '14px', margin: '0 0 15px 0' }}>{item.description}</p>
                        <p style={{ fontSize: '13px', margin: 0, color: '#1B4332' }}>
                          To order: Text "ORDER {item.id},quantity,special request" to our number
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '30px' }}>
          {restaurants.map(restaurant => (
            <div 
              key={restaurant.id} 
              style={{ 
                border: '1px solid #eee', 
                borderRadius: '12px', 
                padding: '20px',
                boxShadow: '0 2px 10px rgba(0,0,0,0.05)',
                cursor: 'pointer',
                transition: 'transform 0.2s, box-shadow 0.2s'
              }}
              onClick={() => handleRestaurantClick(restaurant)}
              onMouseOver={e => {
                e.currentTarget.style.transform = 'translateY(-5px)';
                e.currentTarget.style.boxShadow = '0 5px 15px rgba(0,0,0,0.1)';
              }}
              onMouseOut={e => {
                e.currentTarget.style.transform = 'translateY(0)';
                e.currentTarget.style.boxShadow = '0 2px 10px rgba(0,0,0,0.05)';
              }}
            >
              <h3 style={{ fontSize: '24px', marginBottom: '10px', color: '#1B4332' }}>{restaurant.restaurant_name}</h3>
              <div style={{ textAlign: 'center', marginTop: '20px' }}>
                <span style={{ 
                  display: 'inline-block', 
                  background: '#1B4332', 
                  color: 'white', 
                  padding: '8px 16px', 
                  borderRadius: '4px',
                  fontWeight: 'bold'
                }}>
                  View Menu
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
};

export default RestaurantsSection;
