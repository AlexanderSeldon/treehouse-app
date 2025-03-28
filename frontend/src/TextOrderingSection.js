import React from 'react';

function TextOrderingSection() {
 return (
   <section style={{marginBottom: '50px', padding: '40px 20px', borderRadius: '10px', border: '1px solid #eee'}}>
     <h2 style={{fontSize: '28px', textAlign: 'center', marginBottom: '30px'}}>How to Order by Text</h2>
     
     <div style={{
       display: 'grid', 
       gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', 
       gap: '20px',
       maxWidth: '1000px',
       margin: '0 auto'
     }}>
       {/* Step 1 */}
       <div style={{
         border: '1px solid #ddd', 
         borderRadius: '8px', 
         padding: '20px',
         backgroundColor: '#f9f9f9'
       }}>
         <h3 style={{color: '#1B4332', marginBottom: '15px'}}>Step 1: Text "MENU"</h3>
         <div style={{
           border: '1px solid #ddd',
           borderRadius: '12px',
           padding: '15px',
           backgroundColor: 'white',
           marginBottom: '15px'
         }}>
           <div style={{
             backgroundColor: '#e6f7ff',
             borderRadius: '12px',
             padding: '10px 15px',
             marginBottom: '15px',
             display: 'inline-block',
             maxWidth: '80%'
           }}>
             <p style={{margin: '0', fontSize: '15px'}}><strong>MENU</strong></p>
           </div>
           <div style={{
             backgroundColor: '#f0f0f0',
             borderRadius: '12px',
             padding: '10px 15px',
             marginLeft: '20%',
             display: 'inline-block',
             maxWidth: '80%'
           }}>
             <p style={{margin: '0', fontSize: '15px'}}>Restaurant Options:</p>
             <p style={{margin: '5px 0 0 0', fontSize: '14px'}}>1. Chick-fil-A</p>
             <p style={{margin: '5px 0 0 0', fontSize: '14px'}}>2. Panda Express</p>
             <p style={{margin: '5px 0 0 0', fontSize: '14px'}}>3. Subway</p>
             <p style={{margin: '5px 0 0 0', fontSize: '14px'}}>...</p>
           </div>
         </div>
         <p style={{fontSize: '14px'}}>Text "MENU" to get a list of available restaurants. Each restaurant includes a link to their menu.</p>
       </div>
       
       {/* Step 2 */}
       <div style={{
         border: '1px solid #ddd', 
         borderRadius: '8px', 
         padding: '20px',
         backgroundColor: '#f9f9f9'
       }}>
         <h3 style={{color: '#1B4332', marginBottom: '15px'}}>Step 2: Text Your Order</h3>
         <div style={{
           border: '1px solid #ddd',
           borderRadius: '12px',
           padding: '15px',
           backgroundColor: 'white',
           marginBottom: '15px'
         }}>
           <div style={{
             backgroundColor: '#e6f7ff',
             borderRadius: '12px',
             padding: '10px 15px',
             marginBottom: '15px',
             display: 'inline-block',
             maxWidth: '80%'
           }}>
             <p style={{margin: '0', fontSize: '15px'}}><strong>ORDER 2 burritos from Chipotle with extra guac and a side of chips at Thomas Beckham Hall</strong></p>
           </div>
           <div style={{
             backgroundColor: '#f0f0f0',
             borderRadius: '12px',
             padding: '10px 15px',
             marginLeft: '20%',
             display: 'inline-block',
             maxWidth: '80%'
           }}>
             <p style={{margin: '0', fontSize: '15px'}}>Got it! Your order: 2 burritos from Chipotle with extra guac and a side of chips at Thomas Beckham Hall.</p>
             <p style={{margin: '5px 0 0 0', fontSize: '14px'}}>Text 'PAY' to receive a payment link.</p>
           </div>
         </div>
         <p style={{fontSize: '14px'}}>Text "ORDER" followed by what you want from any restaurant. Be specific and include any special requests and your dorm/aprtment name.</p>
       </div>
       
       {/* Step 3 */}
       <div style={{
         border: '1px solid #ddd', 
         borderRadius: '8px', 
         padding: '20px',
         backgroundColor: '#f9f9f9'
       }}>
         <h3 style={{color: '#1B4332', marginBottom: '15px'}}>Step 3: Text "PAY"</h3>
         <div style={{
           border: '1px solid #ddd',
           borderRadius: '12px',
           padding: '15px',
           backgroundColor: 'white',
           marginBottom: '15px'
         }}>
           <div style={{
             backgroundColor: '#e6f7ff',
             borderRadius: '12px',
             padding: '10px 15px',
             marginBottom: '15px',
             display: 'inline-block',
             maxWidth: '80%'
           }}>
             <p style={{margin: '0', fontSize: '15px'}}><strong>PAY</strong></p>
           </div>
           <div style={{
             backgroundColor: '#f0f0f0',
             borderRadius: '12px',
             padding: '10px 15px',
             marginLeft: '20%',
             display: 'inline-block',
             maxWidth: '80%'
           }}>
             <p style={{margin: '0', fontSize: '15px'}}>Here's your payment link:</p>
             <p style={{margin: '5px 0 0 0', fontSize: '14px'}}>[Payment Link]</p>
             <p style={{margin: '5px 0 0 0', fontSize: '14px'}}>Please enter the exact price from the menu & our delivery fee will automatically be added .</p>
           </div>
         </div>
         <p style={{fontSize: '14px'}}>Text "PAY" to get a secure payment link. Enter the exact menu price & our delivery fee will automatically be added.</p>
       </div>
     </div>
     
     <div style={{
       maxWidth: '600px',
       margin: '40px auto 0',
       padding: '20px',
       backgroundColor: '#1B4332',
       color: 'white',
       borderRadius: '8px',
       textAlign: 'center'
     }}>
       <h3 style={{margin: '0 0 10px 0'}}>Don't see a restaurant you want?</h3>
       <p style={{margin: '0 0 15px 0'}}>Call or text (708) 901-1754 to place a special order</p>
       <p style={{margin: '0', fontWeight: 'bold'}}>First-time orders: Pay after you get your food!</p>
     </div>
     
     <div style={{
       maxWidth: '600px',
       margin: '20px auto 0',
       padding: '15px',
       backgroundColor: '#f9f9f9',
       borderRadius: '8px',
       border: '1px solid #ddd',
     }}>
       <p style={{margin: '0', textAlign: 'center', fontWeight: 'bold'}}>
         Remember: You have to order at the 25-30 minute mark of each hour to get your food at the top of the next hour
       </p>
     </div>
   </section>
 );
}

export default TextOrderingSection;
