import React, { useState } from 'react';
import './App.css';

function App() {
  const [phoneNumber, setPhoneNumber] = useState('');
  
  const handleSignup = () => {
    if (phoneNumber) {
      // Handle the signup process
      alert(`Thanks for signing up with ${phoneNumber}! You'll receive food alerts via text.`);
      // Here you would typically send the phone number to your backend
    } else {
      alert('Please enter your phone number to sign up.');
    }
  };
  
  return (
    <div className="App">
      <header style={{padding: '15px 0', borderBottom: '1px solid #eee', position: 'fixed', width: '100%', backgroundColor: 'white', zIndex: 100}}>
        <div style={{display: 'flex', justifyContent: 'space-between', width: '100%', maxWidth: '1200px', margin: '0 auto', padding: '0 20px', alignItems: 'center'}}>
          <div style={{display: 'flex', alignItems: 'center'}}>
            <svg width="40" height="40" viewBox="0 0 1000 800" xmlns="http://www.w3.org/2000/svg" style={{marginRight: '10px'}}>
              <g>
                {/* House shape */}
                <path d="M500 100 L880 380 L880 700 L120 700 L120 380 Z" fill="#1B4332" />
                {/* Chimney */}
                <rect x="750" y="180" width="80" height="200" fill="#1B4332" />
                {/* Leaf inside house */}
                <path d="M500 600 
                         C650 450, 620 350, 500 400 
                         C380 350, 350 450, 500 600" 
                      fill="#FFFFFF" />
              </g>
            </svg>
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
            
            <h2 style={{fontSize: '32px', marginBottom: '10px'}}>Restaurant Delivery for ONLY $2-3</h2>
            <h3 style={{fontSize: '24px', marginBottom: '20px', fontWeight: 'normal'}}>No hidden fees, ever.</h3>
            
            <p style={{marginBottom: '15px'}}>Enter your phone number once to sign up AND order - everything happens by text!</p>
            <p style={{marginBottom: '15px', fontWeight: 'bold'}}>Pickup from a dorm host on your floor or a neighboring floor.</p>
            <p style={{marginBottom: '15px'}}>Order <span style={{fontWeight: 'bold'}}>exactly at the 25-30 minute mark</span> of each hour to get your food at the top of the next hour. We deliver daily from 11am to 10pm.</p>
            <p style={{marginBottom: '25px'}}><span style={{fontWeight: 'bold'}}>Example:</span> Order at 5:25pm, pickup your food from your dorm host at 6:00pm.</p>
            
            <div style={{display: 'flex', flexDirection: 'column', gap: '10px', marginTop: '20px'}}>
              <input 
                type="tel" 
                placeholder="Enter your phone # to sign up & order via text"
                value={phoneNumber}
                onChange={(e) => setPhoneNumber(e.target.value)}
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
            <svg width="100%" height="auto" viewBox="0 0 500 400" xmlns="http://www.w3.org/2000/svg" style={{maxWidth: '400px', boxShadow: '0 4px 10px rgba(0, 0, 0, 0.1)', borderRadius: '10px'}}>
              <g>
                <path d="M250 60 L460 230 L460 350 L40 350 L40 230 Z" fill="#1B4332" />
                <rect x="380" y="120" width="40" height="110" fill="#1B4332" />
                <path d="M250 320 C340 230, 330 180, 260 200 C190 220, 140 270, 160 300 C180 330, 230 340, 250 320" fill="#FFFFFF" />
              </g>
            </svg>
          </div>
        </section>
        
        <section style={{marginBottom: '50px', backgroundColor: '#F5F5F7', padding: '40px 20px', borderRadius: '10px'}}>
          <h2 style={{fontSize: '28px', textAlign: 'center', marginBottom: '30px'}}>How TreeHouse Works</h2>
          
          <div style={{backgroundColor: 'white', borderRadius: '10px', padding: '30px', boxShadow: '0 2px 8px rgba(0, 0, 0, 0.05)'}}>
            <div style={{display: 'flex', flexDirection: 'column', gap: '30px', textAlign: 'center'}}>
              <div>
                <h3 style={{fontSize: '22px', color: '#1B4332', marginBottom: '10px'}}>1. Pay just $2-3 for delivery</h3>
                <p>No service fees. No markups. No subscriptions. Restaurant prices are exactly the same as in-store.</p>
              </div>
              
              <div>
                <h3 style={{fontSize: '22px', color: '#1B4332', marginBottom: '10px'}}>2. Everything happens by text</h3>
                <p>Get text alerts about upcoming deliveries, order via text, and get notifications when your food arrives.</p>
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
              <p>Restaurant delivery for college students<br />Just $2-3. No hidden fees, ever.</p>
            </div>
            
            <div>
              <h3 style={{fontSize: '20px', marginBottom: '15px'}}>Questions? Contact Us</h3>
              <p style={{display: 'flex', alignItems: 'center', marginBottom: '10px'}}>
                <span style={{marginRight: '10px'}}>📞</span>
                Call or Text: (708) 901-1754
              </p>
              <p style={{display: 'flex', alignItems: 'center'}}>
                <span style={{marginRight: '10px'}}>✉️</span>
                Email: support@treehouse.com
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