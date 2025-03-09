import React from 'react';

const TextOrderingSection = () => {
  return (
    <section style={{ marginBottom: '50px', backgroundColor: '#F5F5F7', padding: '40px 20px', borderRadius: '10px' }}>
      <h2 style={{ fontSize: '28px', textAlign: 'center', marginBottom: '30px' }}>How to Order via Text</h2>
      
      <div style={{ backgroundColor: 'white', borderRadius: '10px', padding: '30px', boxShadow: '0 2px 8px rgba(0, 0, 0, 0.05)' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '30px' }}>
          <div>
            <h3 style={{ fontSize: '22px', color: '#1B4332', marginBottom: '10px' }}>1. Text "MENU" to get started</h3>
            <p>Send a text message with the word "MENU" to our number to receive a list of available restaurants.</p>
          </div>
          
          <div>
            <h3 style={{ fontSize: '22px', color: '#1B4332', marginBottom: '10px' }}>2. Reply with a restaurant number</h3>
            <p>Once you receive the restaurant list, reply with the number of the restaurant you want to order from.</p>
          </div>
          
          <div>
            <h3 style={{ fontSize: '22px', color: '#1B4332', marginBottom: '10px' }}>3. Place your order by text</h3>
            <p>After receiving the menu, text your order in this format:</p>
            <div style={{ backgroundColor: '#F5F5F7', padding: '15px', borderRadius: '6px', fontFamily: 'monospace', marginTop: '10px' }}>
              ORDER item_id,quantity,special request
            </div>
            <p style={{ marginTop: '10px' }}>For example: <strong>ORDER 3,2,extra sauce</strong> to order 2 portions of item #3 with extra sauce.</p>
          </div>
          
          <div>
            <h3 style={{ fontSize: '22px', color: '#1B4332', marginBottom: '10px' }}>4. Pickup your order</h3>
            <p>You'll receive a confirmation text with your order details. Your food will be ready for pickup from your dorm host at the top of the next hour.</p>
          </div>
        </div>
      </div>
    </section>
  );
};

export default TextOrderingSection;
