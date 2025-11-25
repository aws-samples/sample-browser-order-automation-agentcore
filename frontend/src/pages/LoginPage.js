import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  Container, 
  Header, 
  FormField, 
  Input, 
  Button, 
  SpaceBetween, 
  Alert
} from '@cloudscape-design/components';

const LoginPage = () => {
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const response = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password })
      });

      const data = await response.json();

      if (response.ok && data.success) {
        localStorage.setItem('admin_token', data.token);
        navigate('/');
      } else {
        setError(data.detail || data.error || 'Invalid password');
      }
    } catch {
      setError('Login failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ 
      minHeight: '100vh', 
      display: 'flex', 
      alignItems: 'center', 
      justifyContent: 'center',
      background: '#f1f1f1'
    }}>
      <div style={{ width: '100%', maxWidth: '380px' }}>
        <form onSubmit={handleLogin}>
          <Container
            header={
              <Header variant="h1" description="Enter your credentials to continue">
                Admin Login
              </Header>
            }
          >
            <SpaceBetween size="l">
              {error && (
                <Alert 
                  type="error" 
                  dismissible 
                  onDismiss={() => setError('')}
                >
                  {error}
                </Alert>
              )}
              
              <FormField label="Password">
                <Input
                  type="password"
                  value={password}
                  onChange={({ detail }) => setPassword(detail.value)}
                  placeholder="Enter admin password"
                  autoFocus
                />
              </FormField>

              <Button 
                variant="primary" 
                formAction="submit" 
                loading={loading}
                fullWidth
              >
                Sign In
              </Button>
            </SpaceBetween>
          </Container>
        </form>
      </div>
    </div>
  );
};

export default LoginPage;
