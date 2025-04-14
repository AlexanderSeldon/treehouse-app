import React, { useState, useEffect } from 'react';

const HotSpotSection = () => {
  // Function to generate random order count between 5-6
  const getRandomOrderCount = () => Math.floor(Math.random() * 2) + 5; // 5 or 6
  
  // Create arrays of possible free items for each restaurant
  const freeItemOptions = {
    "Chipotle": ["Free chips & guac", "Free side of queso", "Free drink", "Buy one get one free"],
    "McDonald's": ["Free medium fries", "Free apple pie", "Free McFlurry", "Free hash brown"],
    "Chick-fil-A": ["Free cookie", "Free waffle fries", "Free drink", "Free brownie"],
    "Portillo's": ["Free cheese fries", "Free chocolate cake", "Free drink", "Free onion rings"],
    "Starbucks": ["Free cookie", "Free cake pop", "Free bakery item", "Free upsize"],
    "Raising Cane's": ["Free Texas toast", "Free coleslaw", "Free sauce", "Free drink"],
    "Subway": ["Free cookie", "Free chips", "Free drink", "Free 6-inch sub"],
    "Panda Express": ["Free eggroll", "Free rangoon", "Free drink", "Free side"],
    "Five Guys": ["Free small fries", "Free drink", "Free peanuts", "Free bacon topping"]
  };
  
  // Function to get a random free item for a restaurant
  const getRandomFreeItem = (restaurantName) => {
    const options = freeItemOptions[restaurantName] || ["Free item"];
    return options[Math.floor(Math.random() * options.length)];
  };
  
  // Restaurant data with initial random order counts and free item deals
  const [hotRestaurants, setHotRestaurants] = useState([
    { 
      name: "Chipotle", 
      fee: 4.00, 
      orders: 5, 
      fixed: true, 
      isHighTraffic: false, 
      isSecondary: false,
      freeItem: getRandomFreeItem("Chipotle")
    },
    { 
      name: "McDonald's", 
      fee: 4.00, 
      orders: 6, 
      fixed: true, 
      isHighTraffic: false, 
      isSecondary: false,
      freeItem: getRandomFreeItem("McDonald's")
    },
    { 
      name: "Chick-fil-A", 
      fee: 4.00, 
      orders: 5, 
      fixed: true, 
      isHighTraffic: false, 
      isSecondary: false,
      freeItem: getRandomFreeItem("Chick-fil-A")
    },
    { 
      name: "Portillo's", 
      fee: 4.00, 
      orders: 5, 
      fixed: false, 
      isHighTraffic: false, 
      isSecondary: false,
      freeItem: getRandomFreeItem("Portillo's")
    },
    { 
      name: "Starbucks", 
      fee: 4.00, 
      orders: 6, 
      fixed: false, 
      isHighTraffic: false, 
      isSecondary: false,
      freeItem: getRandomFreeItem("Starbucks")
    },
  ]);
  
  const [otherRestaurants, setOtherRestaurants] = useState([
    { name: "Raising Cane's", fee: 7.99, freeItem: getRandomFreeItem("Raising Cane's") },
    { name: "Subway", fee: 8.99, freeItem: getRandomFreeItem("Subway") },
    { name: "Panda Express", fee: 7.49, freeItem: getRandomFreeItem("Panda Express") },
    { name: "Five Guys", fee: 9.99, freeItem: getRandomFreeItem("Five Guys") },
  ]);
  
  const [timeRemaining, setTimeRemaining] = useState(0);
  const [nextOrderWindow, setNextOrderWindow] = useState('');
  const [orderCutoffTime, setOrderCutoffTime] = useState('');
  const [batchCount, setBatchCount] = useState(0);
  const [showShareModal, setShowShareModal] = useState(false);
  const [selectedRestaurant, setSelectedRestaurant] = useState(null);
  const [isOperatingHours, setIsOperatingHours] = useState(true);
  
  // Maximum batch size
  const MAX_BATCH_SIZE = 10;
  
  // Set initial high traffic restaurant
  useEffect(() => {
    // Run this only once at component initialization
    const initialHotRestaurants = [...hotRestaurants];
    
    // Randomly select the high traffic restaurant (9 orders)
    const highTrafficIndex = Math.floor(Math.random() * initialHotRestaurants.length);
    
    // Randomly select the secondary restaurant (7 orders)
    let secondaryIndex;
    do {
      secondaryIndex = Math.floor(Math.random() * initialHotRestaurants.length);
    } while (secondaryIndex === highTrafficIndex);
    
    initialHotRestaurants.forEach((r, i) => {
      if (i === highTrafficIndex) {
        // Set high traffic restaurant (9 orders)
        r.isHighTraffic = true;
        r.isSecondary = false;
        r.orders = 9;
      } else if (i === secondaryIndex) {
        // Set secondary restaurant (7 orders)
        r.isHighTraffic = false;
        r.isSecondary = true;
        r.orders = 7;
      } else {
        // Set other restaurants (5-6 orders)
        r.isHighTraffic = false;
        r.isSecondary = false;
        r.orders = getRandomOrderCount();
      }
    });
    
    setHotRestaurants(initialHotRestaurants);
  }, []);
  
  // Calculate time until next ordering window with operating hours (11am-10pm)
  useEffect(() => {
    const calculateTimeRemaining = () => {
      const now = new Date();
      const currentHours = now.getHours();
      const minutes = now.getMinutes();
      
      // Check if we're within operating hours (11am-10pm)
      const isWithinOperatingHours = currentHours >= 11 && currentHours < 22; // 11am to 10pm
      setIsOperatingHours(isWithinOperatingHours);
      
      if (!isWithinOperatingHours) {
        // If we're outside operating hours, set time to next opening
        const nextOpeningTime = new Date(now);
        
        if (currentHours < 11) {
          // It's morning before opening, set to 11am today
          nextOpeningTime.setHours(11, 0, 0, 0);
        } else {
          // It's after closing, set to 11am tomorrow
          nextOpeningTime.setDate(nextOpeningTime.getDate() + 1);
          nextOpeningTime.setHours(11, 0, 0, 0);
        }
        
        const diffSeconds = Math.floor((nextOpeningTime - now) / 1000);
        setTimeRemaining(diffSeconds);
        
        // Format next opening time display
        const ampm = nextOpeningTime.getHours() >= 12 ? 'PM' : 'AM';
        const displayHours = nextOpeningTime.getHours() % 12 || 12;
        setNextOrderWindow(`${displayHours}:00 ${ampm}`);
        
        return;
      }
      
      // Within operating hours, calculate time to next ordering window (:25 or :55)
      let nextMinute;
      let cutoffMinute;
      
      // Define ordering windows at :25-:30, :55-:00, etc.
      if (minutes < 25) {
        nextMinute = 25;
        cutoffMinute = 30;
      } else if (minutes < 55) {
        nextMinute = 55;
        cutoffMinute = 0; // This becomes 0 for the next hour
      } else {
        nextMinute = 25; // Next hour's window
        cutoffMinute = 30;
      }
      
      const nextTime = new Date(now);
      nextTime.setMinutes(nextMinute, 0, 0);
      
      // Calculate cutoff time
      const cutoffTime = new Date(nextTime);
      if (nextMinute === 55) {
        // If next minute is 55, cutoff is at 00 of next hour
        cutoffTime.setHours(cutoffTime.getHours() + 1);
        cutoffTime.setMinutes(0, 0, 0);
      } else {
        // Otherwise, cutoff is at 30 of this hour
        cutoffTime.setMinutes(30, 0, 0);
      }
      
      if (minutes >= 55) {
        nextTime.setHours(nextTime.getHours() + 1);
        
        // Check if next window would be after closing time
        if (nextTime.getHours() >= 22) {
          // Next batch would be after closing, so point to opening time tomorrow
          nextTime.setDate(nextTime.getDate() + 1);
          nextTime.setHours(11, 0, 0, 0);
          
          // Also update cutoff time
          cutoffTime.setDate(cutoffTime.getDate() + 1);
          cutoffTime.setHours(11, 30, 0, 0);
        }
      }
      
      // Calculate difference in seconds
      const diffSeconds = Math.floor((nextTime - now) / 1000);
      setTimeRemaining(diffSeconds);
      
      // Format next order window time display
      const ampm = nextTime.getHours() >= 12 ? 'PM' : 'AM';
      const displayHours = nextTime.getHours() % 12 || 12;
      setNextOrderWindow(`${displayHours}:${nextMinute.toString().padStart(2, '0')} ${ampm}`);
      
      // Format cutoff time display
      const cutoffAmpm = cutoffTime.getHours() >= 12 ? 'PM' : 'AM';
      const cutoffHours = cutoffTime.getHours() % 12 || 12;
      const cutoffMinuteStr = cutoffTime.getMinutes().toString().padStart(2, '0');
      setOrderCutoffTime(`${cutoffHours}:${cutoffMinuteStr} ${cutoffAmpm}`);
    };
    
    calculateTimeRemaining();
    const timer = setInterval(calculateTimeRemaining, 1000);
    return () => clearInterval(timer);
  }, []);
  
  // Format remaining time as MM:SS
  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };
  
  // Rotate restaurants and simulate orders
  useEffect(() => {
    // This effect handles both order simulation and new batch creation
    const simulateOrderChanges = () => {
      const newHotRestaurants = [...hotRestaurants];
      
      // For each restaurant, ONLY INCREASE orders, never decrease
      newHotRestaurants.forEach(r => {
        if (!r.isHighTraffic && !r.isSecondary) {
          // Regular restaurants - only potentially increase, never decrease
          if (r.orders < 6) {
            // 30% chance to increase by 1
            const shouldIncrease = Math.random() < 0.3;
            if (shouldIncrease) {
              r.orders += 1;
            }
          }
        }
        // High traffic and secondary restaurants stay at their fixed values
      });
      
      setHotRestaurants(newHotRestaurants);
    };
    
    // Handle batch rotation when timer hits zero
    const checkForNewBatch = () => {
      // Check if we're at a batch boundary (every 30 minutes)
      const now = new Date();
      const currentHours = now.getHours();
      const minutes = now.getMinutes();
      const seconds = now.getSeconds();
      
      // Only create new batches during operating hours
      if (currentHours >= 11 && currentHours < 22 && (minutes === 25 || minutes === 55) && seconds === 0) {
        // Time for a new batch!
        createNewBatch();
      }
    };
    
    // Create a new batch with rotated restaurants and new deals
    const createNewBatch = () => {
      setBatchCount(prev => prev + 1);
      
      const newHotRestaurants = [...hotRestaurants];
      
      // Keep the fixed restaurants
      const fixedRestaurants = newHotRestaurants.filter(r => r.fixed);
      const rotatableRestaurants = newHotRestaurants.filter(r => !r.fixed);
      
      // Get 2 random restaurants from otherRestaurants to swap in
      const otherRestaurantsCopy = [...otherRestaurants];
      const newRestaurants = [];
      
      // Pick 2 random restaurants to add to the hot list
      for (let i = 0; i < 2; i++) {
        if (otherRestaurantsCopy.length > 0) {
          const randomIndex = Math.floor(Math.random() * otherRestaurantsCopy.length);
          const selectedRestaurant = otherRestaurantsCopy.splice(randomIndex, 1)[0];
          
          // Convert to hot restaurant format and set fee to $4
          newRestaurants.push({
            name: selectedRestaurant.name,
            fee: 4.00,
            orders: getRandomOrderCount(), // Random order count 5-6
            fixed: false,
            isHighTraffic: false,
            isSecondary: false,
            freeItem: getRandomFreeItem(selectedRestaurant.name) // New random free item
          });
        }
      }
      
      // Get restaurants to move to "other" category
      const restaurantsToMove = [];
      if (rotatableRestaurants.length > 0) {
        for (let i = 0; i < Math.min(2, rotatableRestaurants.length); i++) {
          restaurantsToMove.push({
            name: rotatableRestaurants[i].name,
            fee: 7.99 + Math.random() * 2, // Random fee between 7.99 and 9.99
            freeItem: getRandomFreeItem(rotatableRestaurants[i].name) // New random free item
          });
        }
      }
      
      // Create new hot restaurants list: fixed + new selections
      // Also assign new free items to fixed restaurants
      const finalHotRestaurants = [
        ...fixedRestaurants.map(r => ({
          ...r, 
          orders: getRandomOrderCount(), 
          isHighTraffic: false, 
          isSecondary: false,
          freeItem: getRandomFreeItem(r.name) // New random free item
        })),
        ...newRestaurants
      ];
      
      // Randomly select a different restaurant to be high traffic each batch
      // Make sure to pick a restaurant that wasn't high traffic in the previous batch
      let highTrafficIndex;
      do {
        highTrafficIndex = Math.floor(Math.random() * finalHotRestaurants.length);
      } while (newHotRestaurants.findIndex(r => r.isHighTraffic) === highTrafficIndex);
      
      finalHotRestaurants[highTrafficIndex].isHighTraffic = true;
      finalHotRestaurants[highTrafficIndex].orders = 9;
      
      // Randomly select a different restaurant to be secondary
      let secondaryIndex;
      do {
        secondaryIndex = Math.floor(Math.random() * finalHotRestaurants.length);
      } while (secondaryIndex === highTrafficIndex);
      
      finalHotRestaurants[secondaryIndex].isSecondary = true;
      finalHotRestaurants[secondaryIndex].orders = 7;
      
      // Create new other restaurants list with new free items
      const finalOtherRestaurants = [
        ...otherRestaurantsCopy.map(r => ({
          ...r,
          freeItem: getRandomFreeItem(r.name) // New random free item
        })),
        ...restaurantsToMove
      ];
      
      // Update state
      setHotRestaurants(finalHotRestaurants);
      setOtherRestaurants(finalOtherRestaurants);
    };
    
    // Set up intervals for all effects
    const orderSimulator = setInterval(simulateOrderChanges, 30000); // Every 30 seconds
    const batchChecker = setInterval(checkForNewBatch, 1000); // Check every second
    
    return () => {
      clearInterval(orderSimulator);
      clearInterval(batchChecker);
    };
  }, [hotRestaurants, otherRestaurants, batchCount]);
  
  // Handle share button click
  const handleShare = (restaurant) => {
    setSelectedRestaurant(restaurant);
    
    // Generate share message with free item deal
    const shareText = `Join me in ordering from ${restaurant.name} through TreeHouse! Only $${restaurant.fee.toFixed(2)} delivery fee. Text "order" followed by what you want to (708) 901-1754 to order now! Share this deal to get ${restaurant.freeItem}!`;
    
    // Try to use Web Share API if available
    if (navigator.share) {
      navigator.share({
        title: 'TreeHouse Food Delivery',
        text: shareText,
        url: 'https://treehouseneighbor.com'
      })
      .then(() => {
        console.log('Shared successfully');
        // Show a confirmation alert about the free item
        alert(`Thanks for sharing! Mention this share when ordering to claim your ${restaurant.freeItem}!`);
      })
      .catch((error) => {
        console.log('Error sharing:', error);
        // Fall back to showing modal
        setShowShareModal(true);
      });
    } else {
      // Web Share API not available, show our custom modal
      setShowShareModal(true);
    }
  };
  
  // Handle direct order button click
  const handleOrder = (restaurant) => {
    // Create SMS URL to directly start an order
    const orderText = `ORDER from ${restaurant.name}`;
    const smsUri = `sms:7089011754?&body=${encodeURIComponent(orderText)}`;
    window.location.href = smsUri;
  };
  
  // Close share modal
  const closeShareModal = () => {
    setShowShareModal(false);
    setSelectedRestaurant(null);
  };
  
  // Generate text message url for sharing
  const getTextMessageUrl = (restaurant) => {
    const shareText = `Join me in ordering from ${restaurant.name} through TreeHouse! Only $${restaurant.fee.toFixed(2)} delivery fee. Text "order" followed by what you want to (708) 901-1754 to order now! Share this deal to get ${restaurant.freeItem}!`;
    return `sms:?&body=${encodeURIComponent(shareText)}`;
  };
  
  // Calculate batch progress for a restaurant
  const getBatchProgress = (restaurant) => {
    const percentFull = (restaurant.orders / MAX_BATCH_SIZE) * 100;
    const remainingSpots = MAX_BATCH_SIZE - restaurant.orders;
    
    let statusMessage = '';
    let statusColor = '';
    
    if (percentFull < 30) {
      statusMessage = `${remainingSpots} spots left`;
      statusColor = '#28a745'; // Green
    } else if (percentFull < 70) {
      statusMessage = `${remainingSpots} spots left`;
      statusColor = '#17a2b8'; // Blue
    } else if (percentFull < 100) {
      statusMessage = `Only ${remainingSpots} spots left!`;
      statusColor = '#dc3545'; // Red
    } else {
      statusMessage = 'Batch full!';
      statusColor = '#6c757d'; // Gray
    }
    
    return {
      message: statusMessage,
      color: statusColor,
      percent: percentFull,
      remaining: remainingSpots
    };
  };
  
  return (
    <section style={{backgroundColor: '#F0F7F4', padding: '30px 20px', borderRadius: '10px', marginBottom: '40px'}}>
      <h2 style={{fontSize: '28px', textAlign: 'center', marginBottom: '20px'}}>Today's Hot Spots</h2>
      
      <div style={{textAlign: 'center', marginBottom: '25px'}}>
        <div style={{backgroundColor: '#1B4332', color: 'white', display: 'inline-block', padding: '10px 20px', borderRadius: '8px', fontWeight: 'bold'}}>
          {isOperatingHours ? (
            <>Next order window opens in: <span style={{fontSize: '18px'}}>{formatTime(timeRemaining)}</span></>
          ) : (
            <>We're currently closed. Opening in: <span style={{fontSize: '18px'}}>{formatTime(timeRemaining)}</span></>
          )}
        </div>
        {isOperatingHours ? (
          <p style={{marginTop: '10px'}}>Order no later than {orderCutoffTime} or wait for next batch if spots fill up</p>
        ) : (
          <p style={{marginTop: '10px'}}>We're open 11:00 AM - 10:00 PM. Next opening: {nextOrderWindow}</p>
        )}
        <p style={{marginTop: '5px', fontSize: '14px', fontStyle: 'italic'}}>A dedicated driver is assigned to each batch, optimizing delivery efficiency!</p>
        <p style={{marginTop: '5px', fontSize: '14px', color: '#dc3545', fontWeight: 'bold'}}>
          Free item deals change with each new batch window!
        </p>
      </div>
      
      <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '20px'}}>
        <div>
          <h3 style={{textAlign: 'center', marginBottom: '15px', color: '#1B4332'}}>🔥 Trending Restaurants</h3>
          <div style={{backgroundColor: 'white', borderRadius: '8px', padding: '15px', boxShadow: '0 2px 8px rgba(0,0,0,0.08)'}}>
            {hotRestaurants.map((restaurant, index) => {
              // Get progress for this specific restaurant
              const progress = getBatchProgress(restaurant);
              
              return (
                <div key={index} style={{
                  display: 'flex', 
                  flexDirection: 'column',
                  padding: '12px',
                  borderBottom: index < hotRestaurants.length - 1 ? '1px solid #eee' : 'none'
                }}>
                  <div style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    marginBottom: '8px'
                  }}>
                    <div>
                      <strong>{restaurant.name}</strong>
                      {restaurant.orders > 0 && 
                        <span style={{marginLeft: '10px', color: '#FF6B6B', fontWeight: 'bold'}}>
                          {restaurant.orders} people ordering!
                        </span>
                      }
                    </div>
                    <div style={{
                      backgroundColor: '#d4edda', 
                      color: '#155724', 
                      padding: '4px 8px', 
                      borderRadius: '4px', 
                      fontWeight: 'bold'
                    }}>
                      ${restaurant.fee.toFixed(2)} delivery
                    </div>
                  </div>
                  
                  {/* Free item deal banner */}
                  <div style={{
                    backgroundColor: '#FFF3CD',
                    borderRadius: '4px',
                    padding: '6px 10px',
                    marginBottom: '8px',
                    display: 'flex',
                    alignItems: 'center'
                  }}>
                    <span style={{
                      fontSize: '16px',
                      marginRight: '5px'
                    }}>
                      🎁
                    </span>
                    <span style={{
                      color: '#856404',
                      fontSize: '13px',
                      fontWeight: 'bold'
                    }}>
                      DEAL: Share with a friend to get {restaurant.freeItem}
                    </span>
                  </div>
                  
                  {/* Restaurant-specific batch indicator */}
                  <div style={{
                    margin: '8px 0',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px'
                  }}>
                    <div style={{
                      flex: 1,
                      height: '6px',
                      backgroundColor: '#e9ecef',
                      borderRadius: '3px',
                      overflow: 'hidden'
                    }}>
                      <div style={{
                        height: '100%',
                        width: `${progress.percent > 100 ? 100 : progress.percent}%`,
                        backgroundColor: progress.color,
                        transition: 'width 0.5s ease'
                      }}></div>
                    </div>
                    <div style={{
                      fontSize: '12px',
                      fontWeight: 'bold',
                      color: progress.color,
                      whiteSpace: 'nowrap'
                    }}>
                      {restaurant.orders} of {MAX_BATCH_SIZE} - {progress.message}
                    </div>
                  </div>
                  
                  {/* Action Buttons */}
                  <div style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    marginTop: '8px'
                  }}>
                    <button 
                      onClick={() => handleOrder(restaurant)}
                      style={{
                        backgroundColor: isOperatingHours ? '#1B4332' : '#6c757d',
                        color: 'white',
                        border: 'none',
                        borderRadius: '4px',
                        padding: '6px 12px',
                        fontWeight: 'bold',
                        cursor: isOperatingHours ? 'pointer' : 'not-allowed',
                        flex: '1',
                        marginRight: '8px'
                      }}
                      disabled={!isOperatingHours}
                    >
                      Order Now
                    </button>
                    <button 
                      onClick={() => handleShare(restaurant)}
                      style={{
                        backgroundColor: '#3B82F6',
                        color: 'white',
                        border: 'none',
                        borderRadius: '4px',
                        padding: '6px 12px',
                        fontWeight: 'bold',
                        cursor: 'pointer',
                        flex: '1'
                      }}
                    >
                      Share & Get Free Item
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
        
        <div>
          <h3 style={{textAlign: 'center', marginBottom: '15px', color: '#666'}}>Other Available Restaurants</h3>
          <div style={{backgroundColor: 'white', borderRadius: '8px', padding: '15px', boxShadow: '0 2px 8px rgba(0,0,0,0.08)', display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '200px'}}>
            <div style={{textAlign: 'center', padding: '20px'}}>
              <p style={{fontSize: '16px', color: '#666', fontWeight: 'bold', marginBottom: '10px'}}>
                Any other restaurant will be $7-9 for delivery
              </p>
              <p style={{fontSize: '14px', color: '#666', fontStyle: 'italic'}}>
                (still way less than DoorDash!)
              </p>
            </div>
          </div>
        </div>
      </div>
      
      <div style={{marginTop: '25px', textAlign: 'center'}}>
        <p style={{fontWeight: 'bold', color: '#1B4332'}}>
          Text "MENU" to (708) 901-1754 to order now!
        </p>
        {!isOperatingHours && (
          <p style={{color: '#dc3545', fontStyle: 'italic', marginTop: '5px'}}>
            Note: Orders will be processed when we open at 11:00 AM
          </p>
        )}
      </div>
      
      {/* Share Modal */}
      {showShareModal && selectedRestaurant && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.5)',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          zIndex: 1000
        }}>
          <div style={{
            backgroundColor: 'white',
            borderRadius: '8px',
            padding: '20px',
            maxWidth: '400px',
            width: '90%'
          }}>
            <h3 style={{marginTop: 0}}>Share {selectedRestaurant.name} Deal</h3>
            <p>Share this deal with friends to save on delivery!</p>
            <div style={{
              backgroundColor: '#FFF3CD',
              borderRadius: '4px',
              padding: '8px 12px',
              marginBottom: '15px',
              display: 'flex',
              alignItems: 'center',
              color: '#856404',
              fontSize: '14px',
              fontWeight: 'bold'
            }}>
              <span style={{fontSize: '18px', marginRight: '8px'}}>🎁</span>
              BONUS: You'll get {selectedRestaurant.freeItem} when you share!
            </div>
            <div style={{
              marginBottom: '20px',
              padding: '10px',
              backgroundColor: '#f8f9fa',
              borderRadius: '4px',
              border: '1px solid #dee2e6'
            }}>
              Join me in ordering from {selectedRestaurant.name} through TreeHouse! Only ${selectedRestaurant.fee.toFixed(2)} delivery fee. Text "order" followed by what you want to (708) 901-1754 to order now! Share this deal to get {selectedRestaurant.freeItem}!
            </div>
            <div style={{
              display: 'flex',
              justifyContent: 'space-between'
            }}>
              <a 
                href={getTextMessageUrl(selectedRestaurant)}
                style={{
                  backgroundColor: '#28a745',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  padding: '10px 15px',
                  textDecoration: 'none',
                  fontWeight: 'bold',
                  flex: '1',
                  marginRight: '10px',
                  textAlign: 'center'
                }}
                onClick={() => {
                  // Show a confirmation alert after the user has interacted with the share
                  setTimeout(() => {
                    alert(`Thanks for sharing! Mention this share when ordering to claim your ${selectedRestaurant.freeItem}!`);
                    closeShareModal();
                  }, 1000);
                }}
              >
                Text Friends
              </a>
              <button 
                onClick={closeShareModal}
                style={{
                  backgroundColor: '#6c757d',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  padding: '10px 15px',
                  fontWeight: 'bold',
                  cursor: 'pointer',
                  flex: '1'
                }}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
};

export default HotSpotSection;
