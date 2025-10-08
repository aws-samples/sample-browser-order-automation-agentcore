import React, { useState } from 'react';

const MockShop = () => {
  const [cart, setCart] = useState([]);
  const [showCart, setShowCart] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');

  const products = [
    { id: 1, name: 'Apple iPhone 15 Pro Max', price: 1199, rating: 4.5, reviews: 2847, image: '📱', category: 'Electronics', prime: true },
    { id: 2, name: 'Samsung 65" 4K Smart TV', price: 899, rating: 4.3, reviews: 1523, image: '📺', category: 'Electronics', prime: true },
    { id: 3, name: 'Sony WH-1000XM5 Headphones', price: 399, rating: 4.7, reviews: 3241, image: '🎧', category: 'Electronics', prime: true },
    { id: 4, name: 'MacBook Air M3 13-inch', price: 1299, rating: 4.6, reviews: 892, image: '💻', category: 'Computers', prime: true },
    { id: 5, name: 'Nike Air Max 270', price: 150, rating: 4.4, reviews: 5672, image: '👟', category: 'Shoes', prime: false },
    { id: 6, name: 'Instant Pot Duo 7-in-1', price: 89, rating: 4.6, reviews: 12847, image: '🍲', category: 'Kitchen', prime: true },
    { id: 7, name: 'Kindle Paperwhite', price: 139, rating: 4.5, reviews: 8934, image: '📖', category: 'Electronics', prime: true },
    { id: 8, name: 'Dyson V15 Detect Vacuum', price: 749, rating: 4.4, reviews: 2156, image: '🧹', category: 'Home', prime: true },
    { id: 9, name: 'Levi\'s 501 Original Jeans', price: 59, rating: 4.2, reviews: 4523, image: '👖', category: 'Clothing', prime: false },
    { id: 10, name: 'Echo Dot (5th Gen)', price: 49, rating: 4.3, reviews: 15672, image: '🔊', category: 'Electronics', prime: true },
    { id: 11, name: 'Fitbit Charge 6', price: 199, rating: 4.1, reviews: 3456, image: '⌚', category: 'Electronics', prime: true },
    { id: 12, name: 'Ninja Foodi Air Fryer', price: 129, rating: 4.5, reviews: 6789, image: '🍟', category: 'Kitchen', prime: true },
    { id: 13, name: 'Adidas Ultraboost 22', price: 180, rating: 4.3, reviews: 2341, image: '👟', category: 'Shoes', prime: false },
    { id: 14, name: 'Ring Video Doorbell', price: 99, rating: 4.2, reviews: 8765, image: '🚪', category: 'Home', prime: true },
    { id: 15, name: 'Patagonia Down Jacket', price: 299, rating: 4.6, reviews: 1234, image: '🧥', category: 'Clothing', prime: false },
    { id: 16, name: 'iPad Air 5th Generation', price: 599, rating: 4.5, reviews: 2987, image: '📱', category: 'Electronics', prime: true },
    { id: 17, name: 'KitchenAid Stand Mixer', price: 379, rating: 4.7, reviews: 5432, image: '🥧', category: 'Kitchen', prime: true },
    { id: 18, name: 'The North Face Backpack', price: 89, rating: 4.4, reviews: 3456, image: '🎒', category: 'Outdoor', prime: false },
    { id: 19, name: 'Bose SoundLink Flex', price: 149, rating: 4.3, reviews: 2876, image: '🔊', category: 'Electronics', prime: true },
    { id: 20, name: 'Allbirds Tree Runners', price: 98, rating: 4.1, reviews: 4567, image: '👟', category: 'Shoes', prime: false }
  ];

  const addToCart = (product) => {
    setCart(prev => {
      const existing = prev.find(item => item.id === product.id);
      if (existing) {
        return prev.map(item => 
          item.id === product.id 
            ? { ...item, quantity: item.quantity + 1 }
            : item
        );
      }
      return [...prev, { ...product, quantity: 1 }];
    });
  };

  const getTotalPrice = () => {
    return cart.reduce((total, item) => total + (item.price * item.quantity), 0);
  };

  const renderStars = (rating) => {
    const stars = [];
    for (let i = 1; i <= 5; i++) {
      stars.push(
        <span key={i} style={{ color: i <= rating ? '#FF9900' : '#ddd' }}>★</span>
      );
    }
    return stars;
  };

  const filteredProducts = products.filter(product =>
    product.name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div style={{ fontFamily: 'Amazon Ember, Arial, sans-serif', backgroundColor: '#fff' }}>
      {/* Header */}
      <div style={{ backgroundColor: '#232F3E', color: 'white', padding: '8px 0' }}>
        <div style={{ maxWidth: '1200px', margin: '0 auto', display: 'flex', alignItems: 'center', padding: '0 16px' }}>
          <div style={{ fontSize: '24px', fontWeight: 'bold', marginRight: '24px' }}>
            shopzone
          </div>
          
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', maxWidth: '600px' }}>
            <input
              type="text"
              placeholder="Search ShopZone"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              style={{
                flex: 1,
                padding: '8px 12px',
                border: 'none',
                borderRadius: '4px 0 0 4px',
                fontSize: '14px'
              }}
            />
            <button style={{
              padding: '8px 16px',
              backgroundColor: '#FF9900',
              border: 'none',
              borderRadius: '0 4px 4px 0',
              cursor: 'pointer'
            }}>
              🔍
            </button>
          </div>

          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '24px' }}>
            <div style={{ fontSize: '12px' }}>
              <div>Hello, sign in</div>
              <div style={{ fontWeight: 'bold' }}>Account & Lists</div>
            </div>
            <div style={{ fontSize: '12px' }}>
              <div>Returns</div>
              <div style={{ fontWeight: 'bold' }}>& Orders</div>
            </div>
            <div 
              onClick={() => setShowCart(true)}
              style={{ 
                display: 'flex', 
                alignItems: 'center', 
                cursor: 'pointer',
                position: 'relative'
              }}
            >
              <span style={{ fontSize: '24px', marginRight: '4px' }}>🛒</span>
              <span style={{ fontSize: '12px', fontWeight: 'bold' }}>Cart</span>
              {cart.length > 0 && (
                <span style={{
                  position: 'absolute',
                  top: '-8px',
                  right: '-8px',
                  backgroundColor: '#FF9900',
                  color: '#232F3E',
                  borderRadius: '50%',
                  width: '20px',
                  height: '20px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '12px',
                  fontWeight: 'bold'
                }}>
                  {cart.reduce((sum, item) => sum + item.quantity, 0)}
                </span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <div style={{ backgroundColor: '#37475A', color: 'white', padding: '8px 0' }}>
        <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '0 16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '24px', fontSize: '14px' }}>
            <span>All</span>
            <span>Today's Deals</span>
            <span>Customer Service</span>
            <span>Registry</span>
            <span>Gift Cards</span>
            <span>Sell</span>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '16px' }}>
        {/* Prime Banner */}
        <div style={{
          backgroundColor: '#146EB4',
          color: 'white',
          padding: '12px 16px',
          borderRadius: '8px',
          marginBottom: '24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between'
        }}>
          <div>
            <div style={{ fontWeight: 'bold', fontSize: '16px' }}>Prime</div>
            <div style={{ fontSize: '14px' }}>FREE One-Day Delivery</div>
          </div>
          <button style={{
            backgroundColor: 'white',
            color: '#146EB4',
            border: 'none',
            padding: '8px 16px',
            borderRadius: '4px',
            fontWeight: 'bold',
            cursor: 'pointer'
          }}>
            Try Prime
          </button>
        </div>

        {/* Products Grid */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
          gap: '16px'
        }}>
          {filteredProducts.map(product => (
            <div key={product.id} style={{
              border: '1px solid #ddd',
              borderRadius: '8px',
              padding: '16px',
              backgroundColor: 'white',
              cursor: 'pointer',
              transition: 'box-shadow 0.2s',
              ':hover': { boxShadow: '0 4px 8px rgba(0,0,0,0.1)' }
            }}>
              <div style={{ textAlign: 'center', fontSize: '48px', marginBottom: '12px' }}>
                {product.image}
              </div>
              
              <div style={{ fontSize: '16px', fontWeight: '500', marginBottom: '8px', lineHeight: '1.3' }}>
                {product.name}
              </div>
              
              <div style={{ display: 'flex', alignItems: 'center', marginBottom: '8px' }}>
                <div style={{ marginRight: '8px' }}>
                  {renderStars(product.rating)}
                </div>
                <span style={{ fontSize: '14px', color: '#007185' }}>
                  ({product.reviews.toLocaleString()})
                </span>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', marginBottom: '12px' }}>
                <span style={{ fontSize: '24px', fontWeight: 'bold', color: '#B12704' }}>
                  ${product.price}
                </span>
                {product.prime && (
                  <div style={{
                    marginLeft: '12px',
                    backgroundColor: '#146EB4',
                    color: 'white',
                    padding: '2px 6px',
                    borderRadius: '4px',
                    fontSize: '12px',
                    fontWeight: 'bold'
                  }}>
                    Prime
                  </div>
                )}
              </div>

              <div style={{ fontSize: '12px', color: '#565959', marginBottom: '12px' }}>
                FREE delivery tomorrow
              </div>

              <button
                onClick={() => addToCart(product)}
                style={{
                  width: '100%',
                  backgroundColor: '#FF9900',
                  color: '#0F1111',
                  border: 'none',
                  padding: '8px 16px',
                  borderRadius: '20px',
                  fontSize: '14px',
                  fontWeight: 'bold',
                  cursor: 'pointer',
                  marginBottom: '8px'
                }}
              >
                Add to Cart
              </button>

              <button
                style={{
                  width: '100%',
                  backgroundColor: '#FFA41C',
                  color: '#0F1111',
                  border: 'none',
                  padding: '8px 16px',
                  borderRadius: '20px',
                  fontSize: '14px',
                  fontWeight: 'bold',
                  cursor: 'pointer'
                }}
              >
                Buy Now
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Cart Modal */}
      {showCart && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.5)',
          zIndex: 1000,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center'
        }}>
          <div style={{
            backgroundColor: 'white',
            borderRadius: '8px',
            padding: '24px',
            maxWidth: '600px',
            width: '90%',
            maxHeight: '80vh',
            overflow: 'auto'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
              <h2 style={{ margin: 0, fontSize: '24px' }}>Shopping Cart</h2>
              <button
                onClick={() => setShowCart(false)}
                style={{
                  background: 'none',
                  border: 'none',
                  fontSize: '24px',
                  cursor: 'pointer'
                }}
              >
                ×
              </button>
            </div>

            {cart.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '48px 0' }}>
                <div style={{ fontSize: '48px', marginBottom: '16px' }}>🛒</div>
                <div style={{ fontSize: '18px', color: '#565959' }}>Your cart is empty</div>
              </div>
            ) : (
              <>
                {cart.map(item => (
                  <div key={item.id} style={{
                    display: 'flex',
                    alignItems: 'center',
                    padding: '16px 0',
                    borderBottom: '1px solid #ddd'
                  }}>
                    <div style={{ fontSize: '32px', marginRight: '16px' }}>
                      {item.image}
                    </div>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 'bold', marginBottom: '4px' }}>
                        {item.name}
                      </div>
                      <div style={{ color: '#B12704', fontWeight: 'bold' }}>
                        ${item.price}
                      </div>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span>Qty: {item.quantity}</span>
                      <div style={{ fontWeight: 'bold' }}>
                        ${(item.price * item.quantity).toLocaleString()}
                      </div>
                    </div>
                  </div>
                ))}
                
                <div style={{ 
                  display: 'flex', 
                  justifyContent: 'space-between', 
                  alignItems: 'center',
                  padding: '24px 0',
                  fontSize: '20px',
                  fontWeight: 'bold'
                }}>
                  <span>Subtotal ({cart.reduce((sum, item) => sum + item.quantity, 0)} items):</span>
                  <span style={{ color: '#B12704' }}>${getTotalPrice().toLocaleString()}</span>
                </div>

                <button
                  style={{
                    width: '100%',
                    backgroundColor: '#FF9900',
                    color: '#0F1111',
                    border: 'none',
                    padding: '12px 24px',
                    borderRadius: '8px',
                    fontSize: '16px',
                    fontWeight: 'bold',
                    cursor: 'pointer'
                  }}
                  onClick={() => {
                    console.log(`Order placed! Total: $${getTotalPrice().toLocaleString()}`);
                    setCart([]);
                    setShowCart(false);
                  }}
                >
                  Proceed to checkout
                </button>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default MockShop;
