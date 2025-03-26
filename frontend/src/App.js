import React, { useState } from 'react';
import './App.css';
import RestaurantsSection from './RestaurantsSection';
import TextOrderingSection from './TextOrderingSection';
import Logo from './Logo';

function App() {
  // State for user phone number input
  const [phoneNumber, setPhoneNumber] = useState('');
  const [dormBuilding, setDormBuilding] = useState(''); 
  // Signup handler function to connect with backend
  const handleSignup = async () => {
    if (!phoneNumber) {
      alert("Please enter your phone number");
      return;
    }
    
    try {
      const response = await fetch('http://localhost:5001/api/signup', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          phone_number: phoneNumber,
          dorm_building: dormBuilding  // Include dorm building in request
        }),
      });
      
      const data = await response.json();
      
      if (response.ok) {
        // Create a visible element on the page
        const confirmationDiv = document.createElement('div');
        confirmationDiv.style.backgroundColor = '#d4edda';
        confirmationDiv.style.color = '#155724';
        confirmationDiv.style.padding = '12px';
        confirmationDiv.style.margin = '15px 0';
        confirmationDiv.style.borderRadius = '4px';
        confirmationDiv.style.fontWeight = 'bold';
        confirmationDiv.textContent = "Thanks for signing up! You'll receive text alerts for upcoming deliveries.";
        
        // Find the form and insert the confirmation after it
        const form = document.querySelector('.App form') || document.querySelector('.App button').parentNode;
        form.parentNode.insertBefore(confirmationDiv, form.nextSibling);
        
        // Remove it after 5 seconds
        setTimeout(() => {
          confirmationDiv.remove();
        }, 5000);
        
        setPhoneNumber(''); // Clear the input field
        setDormBuilding(''); // Clear dorm selection
      } else {
        alert("Error: " + (data.error || "Something went wrong"));
      }
    } catch (error) {
      console.error("Error:", error);
      alert("Error connecting to server. Please try again later.");
    }
  };
  
  return (
    <div className="App">
      <header style={{padding: '15px 0', borderBottom: '1px solid #eee', position: 'fixed', width: '100%', backgroundColor: 'white', zIndex: 100}}>
        <div style={{display: 'flex', justifyContent: 'space-between', width: '100%', maxWidth: '1200px', margin: '0 auto', padding: '0 20px', alignItems: 'center'}}>
          <div style={{display: 'flex', alignItems: 'center'}}>
            <Logo style={{marginRight: '10px'}} />
            <h1 style={{fontSize: '24px', color: '#1B4332', margin: 0}}>TreeHouse</h1>
          </div>
          <button style={{background: '#1B4332', color: 'white', padding: '8px 16px', border: 'none', borderRadius: '4px', cursor: 'pointer'}}>
            How It Works
          </button>
        </div>
      </header>
      
      <main style={{padding: '20px', paddingTop: '100px', maxWidth: '1200px', margin: '0 auto'}}>
        <section style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '40px', marginBottom: '50px'}}>
          <div>
            <div style={{display: 'inline-flex', alignItems: 'center', backgroundColor: '#1B4332', color: 'white', fontWeight: 'bold', padding: '10px 15px', borderRadius: '8px', marginBottom: '20px'}}>
              ✓ FIRST-TIME ORDERS: PAY AFTER YOU GET YOUR FOOD!
            </div>
            
            <h2 style={{fontSize: '32px', marginBottom: '10px'}}>Restaurant Delivery for ONLY $2-4</h2>
            <h3 style={{fontSize: '24px', marginBottom: '20px', fontWeight: 'normal'}}>No hidden fees, ever.</h3>
            
            <p style={{marginBottom: '15px'}}>Enter your phone number once to sign up AND order - everything happens by text!</p>
            <p style={{marginBottom: '15px', fontWeight: 'bold'}}>Pickup from a dorm host on your floor or a neighboring floor.</p>
            <p style={{marginBottom: '15px'}}>You <span style={{fontWeight: 'bold'}}>have to order exactly at the 25-30 minute mark</span> of each hour to get your food at the top of the next hour. We deliver daily from 11am to 10pm.</p>
            <p style={{marginBottom: '25px'}}><span style={{fontWeight: 'bold'}}>Example:</span> Order at 5:25pm, pickup your food from your dorm host at 6:00pm.</p>
            
            <div style={{display: 'flex', flexDirection: 'column', gap: '10px', marginTop: '20px'}}>
              <input 
                type="tel" 
                placeholder="Enter your phone # to sign up & order via text"
                value={phoneNumber}
                onChange={(e) => setPhoneNumber(e.target.value)}
                style={{padding: '12px', borderRadius: '4px', border: '1px solid #ddd'}}
              />
              <input 
                type="text" 
                placeholder="Enter your dorm/building name"
                value={dormBuilding}
                onChange={(e) => setDormBuilding(e.target.value)}
                style={{padding: '12px', borderRadius: '4px', border: '1px solid #ddd'}}
              />
              <button 
                style={{background: '#1B4332', color: 'white', padding: '12px', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold'}}
                onClick={handleSignup}
              >
                Sign Up & Get Food Alerts
              </button>
            </div>
          </div>
          
          <div style={{display: 'flex', justifyContent: 'center', alignItems: 'center'}}>
            <Logo width="100%" height="auto" style={{maxWidth: '400px', boxShadow: '0 4px 10px rgba(0, 0, 0, 0.1)', borderRadius: '10px'}} />
          </div>
        </section>
        
        {/* Restaurant Links Section */}
        <section style={{marginBottom: '50px', padding: '40px 20px', borderRadius: '10px', border: '1px solid #eee'}}>
          <h2 style={{fontSize: '28px', textAlign: 'center', marginBottom: '30px'}}>Restaurant Menus</h2>
          
          <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '20px'}}>
            {/* Chick-fil-A */}
            <div style={{padding: '20px', borderRadius: '8px', border: '1px solid #ddd', textAlign: 'center'}}>
              <h3 style={{color: '#1B4332', marginBottom: '10px'}}>Chick-fil-A</h3>
              <a href="https://order.chick-fil-a.com/menu" target="_blank" rel="noopener noreferrer" 
                 style={{display: 'inline-block', padding: '8px 16px', background: '#1B4332', color: 'white', 
                        textDecoration: 'none', borderRadius: '4px', fontWeight: 'bold'}}>
                View Menu
              </a>
            </div>
            
            {/* Panda Express */}
            <div style={{padding: '20px', borderRadius: '8px', border: '1px solid #ddd', textAlign: 'center'}}>
              <h3 style={{color: '#1B4332', marginBottom: '10px'}}>Panda Express</h3>
              <a href="https://www.pandaexpress.com/location/roosevelt-canal-px/menu" target="_blank" rel="noopener noreferrer" 
                 style={{display: 'inline-block', padding: '8px 16px', background: '#1B4332', color: 'white', 
                        textDecoration: 'none', borderRadius: '4px', fontWeight: 'bold'}}>
                View Menu
              </a>
            </div>
            
            {/* Subway */}
            <div style={{padding: '20px', borderRadius: '8px', border: '1px solid #ddd', textAlign: 'center'}}>
              <h3 style={{color: '#1B4332', marginBottom: '10px'}}>Subway</h3>
              <a href="https://restaurants.subway.com/united-states/il/chicago/750-s-halsted-st?utm_source=yxt-goog&utm_medium=local&utm_term=acq&utm_content=26444&utm_campaign=evergreen-2020&y_source=1_MTQ5MTY3OTItNzE1LWxvY2F0aW9uLndlYnNpdGU%3D" target="_blank" rel="noopener noreferrer" 
                 style={{display: 'inline-block', padding: '8px 16px', background: '#1B4332', color: 'white', 
                        textDecoration: 'none', borderRadius: '4px', fontWeight: 'bold'}}>
                View Menu
              </a>
            </div>
            
            {/* Jim's Original */}
            <div style={{padding: '20px', borderRadius: '8px', border: '1px solid #ddd', textAlign: 'center'}}>
              <h3 style={{color: '#1B4332', marginBottom: '10px'}}>Jim's Original</h3>
              <a href="http://www.jimsoriginal.com/" target="_blank" rel="noopener noreferrer" 
                 style={{display: 'inline-block', padding: '8px 16px', background: '#1B4332', color: 'white', 
                        textDecoration: 'none', borderRadius: '4px', fontWeight: 'bold'}}>
                View Menu
              </a>
            </div>
            
            {/* Al's Beef */}
            <div style={{padding: '20px', borderRadius: '8px', border: '1px solid #ddd', textAlign: 'center'}}>
              <h3 style={{color: '#1B4332', marginBottom: '10px'}}>Al's Beef</h3>
              <a href="https://www.alsbeef.com/chicago-little-italy-taylor-street" target="_blank" rel="noopener noreferrer" 
                 style={{display: 'inline-block', padding: '8px 16px', background: '#1B4332', color: 'white', 
                        textDecoration: 'none', borderRadius: '4px', fontWeight: 'bold'}}>
                View Menu
              </a>
            </div>
            
            {/* Busy Burger */}
            <div style={{padding: '20px', borderRadius: '8px', border: '1px solid #ddd', textAlign: 'center'}}>
              <h3 style={{color: '#1B4332', marginBottom: '10px'}}>Busy Burger</h3>
              <a href="https://www.busyburger.com/menus" target="_blank" rel="noopener noreferrer" 
                 style={{display: 'inline-block', padding: '8px 16px', background: '#1B4332', color: 'white', 
                        textDecoration: 'none', borderRadius: '4px', fontWeight: 'bold'}}>
                View Menu
              </a>
            </div>
            
            {/* Portillo's */}
            <div style={{padding: '20px', borderRadius: '8px', border: '1px solid #ddd', textAlign: 'center'}}>
              <h3 style={{color: '#1B4332', marginBottom: '10px'}}>Portillo's</h3>
              <a href="https://order.portillos.com/menu/portillos-hot-dogs-chicago/" target="_blank" rel="noopener noreferrer" 
                 style={{display: 'inline-block', padding: '8px 16px', background: '#1B4332', color: 'white', 
                        textDecoration: 'none', borderRadius: '4px', fontWeight: 'bold'}}>
                View Menu
              </a>
            </div>
            
            {/* Chipotle */}
            <div style={{padding: '20px', borderRadius: '8px', border: '1px solid #ddd', textAlign: 'center'}}>
              <h3 style={{color: '#1B4332', marginBottom: '10px'}}>Chipotle</h3>
              <a href="https://locations.chipotle.com/il/chicago/1132-s-clinton-st?utm_source=google&utm_medium=yext&utm_campaign=yext_listings" target="_blank" rel="noopener noreferrer" 
                 style={{display: 'inline-block', padding: '8px 16px', background: '#1B4332', color: 'white', 
                        textDecoration: 'none', borderRadius: '4px', fontWeight: 'bold'}}>
                View Menu
              </a>
            </div>
            
            {/* Dunkin */}
            <div style={{padding: '20px', borderRadius: '8px', border: '1px solid #ddd', textAlign: 'center'}}>
              <h3 style={{color: '#1B4332', marginBottom: '10px'}}>Dunkin</h3>
              <a href="https://locations.dunkindonuts.com/en/il/chicago/750-s-halsted-st-university/349361?utm_source=google&utm_medium=local&utm_campaign=localmaps&utm_content=349361&y_source=1_MTIxMTQ3NTktNzE1LWxvY2F0aW9uLndlYnNpdGU%3D" target="_blank" rel="noopener noreferrer" 
                 style={{display: 'inline-block', padding: '8px 16px', background: '#1B4332', color: 'white', 
                        textDecoration: 'none', borderRadius: '4px', fontWeight: 'bold'}}>
                View Menu
              </a>
            </div>
            
            {/* Au Bon Pain */}
            <div style={{padding: '20px', borderRadius: '8px', border: '1px solid #ddd', textAlign: 'center'}}>
              <h3 style={{color: '#1B4332', marginBottom: '10px'}}>Au Bon Pain</h3>
              <a href="https://www.aubonpain.com/menu" target="_blank" rel="noopener noreferrer" 
                 style={{display: 'inline-block', padding: '8px 16px', background: '#1B4332', color: 'white', 
                        textDecoration: 'none', borderRadius: '4px', fontWeight: 'bold'}}>
                View Menu
              </a>
            </div>
            
            {/* Thai Bowl */}
            <div style={{padding: '20px', borderRadius: '8px', border: '1px solid #ddd', textAlign: 'center'}}>
              <h3 style={{color: '#1B4332', marginBottom: '10px'}}>Thai Bowl</h3>
              <a href="http://places.singleplatform.com/thai-bowl-2/menu?ref=google" target="_blank" rel="noopener noreferrer" 
                 style={{display: 'inline-block', padding: '8px 16px', background: '#1B4332', color: 'white', 
                        textDecoration: 'none', borderRadius: '4px', fontWeight: 'bold'}}>
                View Menu
              </a>
            </div>
            
            {/* Mario's Italian Ice */}
            <div style={{padding: '20px', borderRadius: '8px', border: '1px solid #ddd', textAlign: 'center'}}>
              <h3 style={{color: '#1B4332', marginBottom: '10px'}}>Mario's Italian Ice</h3>
              <a href="http://www.marioslemonade.com/menu" target="_blank" rel="noopener noreferrer" 
                 style={{display: 'inline-block', padding: '8px 16px', background: '#1B4332', color: 'white', 
                        textDecoration: 'none', borderRadius: '4px', fontWeight: 'bold'}}>
                View Menu
              </a>
            </div>
            
            {/* Gather Tea Bar */}
            <div style={{padding: '20px', borderRadius: '8px', border: '1px solid #ddd', textAlign: 'center'}}>
              <h3 style={{color: '#1B4332', marginBottom: '10px'}}>Gather Tea Bar</h3>
              <a href="http://www.gathersteabar.com/" target="_blank" rel="noopener noreferrer" 
                 style={{display: 'inline-block', padding: '8px 16px', background: '#1B4332', color: 'white', 
                        textDecoration: 'none', borderRadius: '4px', fontWeight: 'bold'}}>
                View Menu
              </a>
            </div>
            
            {/* Lulu's Hot Dogs */}
            <div style={{padding: '20px', borderRadius: '8px', border: '1px solid #ddd', textAlign: 'center'}}>
              <h3 style={{color: '#1B4332', marginBottom: '10px'}}>Lulu's Hot Dogs</h3>
              <a href="http://lulushotdogs.com/" target="_blank" rel="noopener noreferrer" 
                 style={{display: 'inline-block', padding: '8px 16px', background: '#1B4332', color: 'white', 
                        textDecoration: 'none', borderRadius: '4px', fontWeight: 'bold'}}>
                View Menu
              </a>
            </div>
          </div>
        </section>
        
        {/* Add the TextOrderingSection component here */}
        <TextOrderingSection />
        
        {/* Ordering Process Section */}
        <section style={{marginBottom: '50px', backgroundColor: '#F5F5F7', padding: '40px 20px', borderRadius: '10px'}}>
          <h2 style={{fontSize: '28px', textAlign: 'center', marginBottom: '30px'}}>How TreeHouse Works</h2>
          
          <div style={{backgroundColor: 'white', borderRadius: '10px', padding: '30px', boxShadow: '0 2px 8px rgba(0, 0, 0, 0.05)'}}>
            <div style={{display: 'flex', flexDirection: 'column', gap: '30px', textAlign: 'center'}}>
              <div>
                <h3 style={{fontSize: '22px', color: '#1B4332', marginBottom: '10px'}}>1. Pay just $2-4 for delivery</h3>
                <p>No service fees. No markups. No subscriptions. Restaurant prices are exactly the same as in-store.</p>
              </div>
              
              <div>
                <h3 style={{fontSize: '22px', color: '#1B4332', marginBottom: '10px'}}>Ordering Process:</h3>
                <ol style={{textAlign: 'left', maxWidth: '400px', margin: '0 auto', lineHeight: '1.6'}}>
                  <li>Browse restaurant menus on our website</li>
                  <li>Text us your order details</li>
                  <li>We send a payment link (you enter menu price, we add delivery fee)</li>
                </ol>
              </div>
              
              <div>
                <h3 style={{fontSize: '22px', color: '#1B4332', marginBottom: '10px'}}>3. Pick up from a host in your dorm</h3>
                <p>A TreeHouse host in your building will have your food. All orders are sealed by the restaurant before delivery.</p>
              </div>
              
              <div>
                <h3 style={{fontSize: '22px', color: '#1B4332'}}>First time ordering? You don't pay until we hand you your food!</h3>
              </div>
            </div>
          </div>
        </section>
      </main>
      
      <footer style={{backgroundColor: '#1D1D1F', color: 'white', padding: '40px 20px'}}>
        <div style={{maxWidth: '1200px', margin: '0 auto'}}>
          <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '30px'}}>
            <div>
              <h3 style={{fontSize: '20px', marginBottom: '15px'}}>TreeHouse</h3>
              <p>Restaurant delivery for college students<br />Just $2-4. No hidden fees, ever.</p>
            </div>
            
            <div>
              <h3 style={{fontSize: '20px', marginBottom: '15px'}}>Questions? Contact Us</h3>
              <p style={{display: 'flex', alignItems: 'center', marginBottom: '10px'}}>
                <span style={{marginRight: '10px'}}>📞</span>
                Call or Text: (708) 901-1754
              </p>
              <p style={{display: 'flex', alignItems: 'center'}}>
                <span style={{marginRight: '10px'}}></span>
              </p>
            </div>
          </div>
          
          <div style={{borderTop: '1px solid rgba(255, 255, 255, 0.1)', marginTop: '30px', paddingTop: '20px', textAlign: 'center', fontSize: '14px'}}>
            <p>&copy; 2025 TreeHouse. All rights reserved.</p>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default App;
