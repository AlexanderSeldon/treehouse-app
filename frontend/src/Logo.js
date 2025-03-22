import React from 'react';
import logoImage from './assets/logo1.png'; // Adjust the path to where your logo is located

function Logo({ width = '40px', height = '40px', style = {} }) {
  return (
    <img 
      src={logoImage}
      alt="TreeHouse Logo"
      width={width}
      height={height}
      style={style}
    />
  );
}

export default Logo;
