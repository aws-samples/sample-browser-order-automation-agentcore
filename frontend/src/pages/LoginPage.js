import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  Container, 
  Header, 
  FormField, 
  Input, 
  Button, 
  SpaceBetween, 
  Alert,
  Box
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
        sessionStorage.setItem('admin_token', data.token);
        navigate('/');
      } else {
        setError(data.detail || 'Invalid password');
      }
    } catch (err) {
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
      background: '#ffffff'
    }}>
      <Container
        header={
          <Header variant="h1">
            <div style={{ textAlign: 'center' }}>
              <span>Authentication Required</span>
            </div>
          </Header>
        }
      >
        <form onSubmit={handleLogin}>
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
                placeholder="Enter password"
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
        </form>
      </Container>
    </div>
  );
};

export default LoginPage;
