import React from 'react';
import logoImage from './assets/logo1.png'; // Adjust the path to where your logo is located

function Logo({ style = {} }) {
  // Removed width and height props to prevent overriding the style object
  
  return (
    <img 
      src={logoImage}
      alt="TreeHouse Logo"
      style={{
        width: '100px',
        height: '100px',
        ...style // This allows additional style properties to be added
      }}
    />
  );
}

export default Logo;
