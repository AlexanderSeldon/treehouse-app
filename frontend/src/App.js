import React, { useState } from 'react';
import './App.css';
import TextOrderingSection from './TextOrderingSection';
import Logo from './Logo';
import frontpageImage from './assets/frontpage.jpg';
import HotSpotSection from './HotSpotSection';

function App() {
 // State for user phone number input
 const [phoneNumber, setPhoneNumber] = useState('');
 const [dormBuilding, setDormBuilding] = useState(''); 
 
 const scrollToHowItWorks = () => {
   const howItWorksSection = document.getElementById('how-it-works-section');
   if (howItWorksSection) {
     howItWorksSection.scrollIntoView({ behavior: 'smooth' });
   }
 };
 
 // Signup handler function to connect with backend
 const handleSignup = async () => {
   if (!phoneNumber) {
     alert("Please enter your phone number");
     return;
   }
   
   try {
     const response = await fetch('/api/signup', {
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
 <div style={{display: 'flex', justifyContent: 'space-between', width: '100%', maxWidth: '1200px', margin: '0 auto', padding: '0 10px', alignItems: 'center'}}>
   <div style={{display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
     <Logo />
   </div>
   <button 
 style={{
   background: '#1B4332', 
   color: 'white', 
   padding: '8px 16px', 
   border: 'none', 
   borderRadius: '4px', 
   cursor: 'pointer',
   marginRight: '15px'  // Increase from 5px to 15px
 }}
 onClick={scrollToHowItWorks}
>
 How It Works
</button>
 </div>
</header>
     
     <main style={{padding: '20px', paddingTop: '150px', maxWidth: '1200px', margin: '0 auto'}}>
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
         
         <div style={{
 display: 'flex', 
 justifyContent: 'center', 
 alignItems: 'center',
 padding: '10px',
 height: 'auto', // Change from fixed height to auto
 width: '100%'
}}>
 <div style={{
   width: '100%',
   maxWidth: '450px',
   // Remove fixed height and use aspect ratio instead
   aspectRatio: '1/1', // This maintains a square shape
   border: '3px solid #1B4332', 
   borderRadius: '12px',
   padding: '4px',
   boxShadow: '0 6px 15px rgba(0, 0, 0, 0.15)',
   background: 'white',
   overflow: 'hidden' // Ensure image doesn't overflow container
 }}>
   <img 
     src={frontpageImage}
     alt="TreeHouse Food Delivery"
     style={{
       width: '100%',
       height: '100%',
       borderRadius: '8px',
       objectFit: 'cover',
     }}
   />
 </div>
</div>
       </section>
       
       {/* Add the HotSpotSection component here */}
       <HotSpotSection />
       
       {/* Add the TextOrderingSection component here */}
       <TextOrderingSection />
       
       {/* Ordering Process Section */}
       <section id="how-it-works-section" style={{marginBottom: '50px', backgroundColor: '#F5F5F7', padding: '40px 20px', borderRadius: '10px'}}>
         <h2 style={{fontSize: '28px', textAlign: 'center', marginBottom: '30px'}}>How TreeHouse Works</h2>
         
         <div style={{backgroundColor: 'white', borderRadius: '10px', padding: '30px', boxShadow: '0 2px 8px rgba(0, 0, 0, 0.05)'}}>
           <div style={{display: 'flex', flexDirection: 'column', gap: '30px', textAlign: 'center'}}>
             <div>
               <h3 style={{fontSize: '22px', color: '#1B4332', marginBottom: '10px'}}>1. Pay just $2-4 for delivery</h3>
               <p>No service fees. No markups. No subscriptions. Restaurant prices are exactly the same as in-store.</p>
             </div>
             
             <div>
               <h3 style={{fontSize: '22px', color: '#1B4332', marginBottom: '10px'}}>2. Ordering Process:</h3>
               <ol style={{textAlign: 'left', maxWidth: '400px', margin: '0 auto', lineHeight: '1.6'}}>
                 <li>We text you the list of restaurants and their menus</li>
                 <li>Yout text us your order details</li>
                 <li>We send a payment link (you enter menu price, plus our delivery fee thats listed)</li>
               </ol>
             </div>
             
             <div>
               <h3 style={{fontSize: '22px', color: '#1B4332', marginBottom: '10px'}}>3. Pick up from a host in your dorm</h3>
               <p>A TreeHouse host in your building will have your food at their dorm room/unit. All orders are sealed by us before delivery.</p>
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
