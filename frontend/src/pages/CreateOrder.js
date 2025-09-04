import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Container,
  Header,
  SpaceBetween,
  Button,
  FormField,
  Input,
  Select,
  Textarea,
  ColumnLayout,
  Alert,
  Box,
  ExpandableSection,
  Link
} from '@cloudscape-design/components';
import ModelSelector from '../components/ModelSelector';

const CreateOrder = ({ addNotification }) => {
  const navigate = useNavigate();
  const [retailers, setRetailers] = useState({});
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({
    // Required fields - minimal for demo
    retailer: 'gucci', // Default to Gucci
    product_url: 'https://www.gucci.com', // Default to Gucci base URL
    product_name: '',
    
    // Optional fields - demo mode
    customer_name: 'Demo Customer',
    customer_email: 'demo@example.com',
    shipping_first_name: 'Demo',
    shipping_last_name: 'User',
    shipping_address_1: '123 Demo Street',
    shipping_city: 'Demo City',
    shipping_state: 'CA',
    shipping_postal_code: '12345',
    shipping_country: 'US',
    
    // Agent will figure these out
    product_size: '',
    product_color: '',
    product_quantity: 1,
    product_price: '',
    shipping_address_2: '',
    automation_method: 'strands_browser', // Default to Strands + Browser Tools + AgentCore Browser
    ai_model: 'us.anthropic.claude-sonnet-4-20250514-v1:0',
    
    // Instructions for agent (optional)
    instructions: ''
  });

  useEffect(() => {
    fetchRetailers();
  }, []);

  const fetchRetailers = async () => {
    try {
      const response = await fetch('/api/config/retailers');
      if (response.ok) {
        const data = await response.json();
        setRetailers(data);
      }
    } catch (error) {
      console.error('Failed to fetch retailers:', error);
    }
  };

  const handleInputChange = (field, value) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const validateForm = () => {
    return formData.retailer && formData.product_name;
  };

  const handleSubmit = async () => {
    setLoading(true);
    try {
      const orderData = {
        customer_name: formData.customer_name,
        customer_email: formData.customer_email,
        retailer: formData.retailer,
        automation_method: formData.automation_method,
        ai_model: formData.ai_model,
        product: {
          url: formData.product_url,
          name: formData.product_name,
          size: formData.product_size || undefined,
          color: formData.product_color || undefined,
          quantity: formData.product_quantity,
          price: formData.product_price ? parseFloat(formData.product_price) : undefined
        },
        shipping_address: {
          first_name: formData.shipping_first_name,
          last_name: formData.shipping_last_name,
          address_line_1: formData.shipping_address_1,
          address_line_2: formData.shipping_address_2 || undefined,
          city: formData.shipping_city,
          state: formData.shipping_state,
          postal_code: formData.shipping_postal_code,
          country: formData.shipping_country
        },

        instructions: formData.instructions || undefined
      };

      const response = await fetch('/api/orders', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(orderData)
      });

      if (!response.ok) {
        throw new Error('Failed to create order');
      }

      const result = await response.json();

      addNotification({
        type: 'success',
        header: 'Order Created',
        content: `Order ${result.order_id} has been created successfully`
      });

      navigate('/dashboard');

    } catch (error) {
      addNotification({
        type: 'error',
        header: 'Order Creation Failed',
        content: `Failed to create order: ${error.message}`
      });
    } finally {
      setLoading(false);
    }
  };

  const retailerOptions = Object.entries(retailers.retailer_configs || {}).map(([key, retailer]) => ({
    label: retailer.name || key,
    value: key
  }));

  // Get selected retailer's base URL for placeholder
  const selectedRetailerConfig = retailers.retailer_configs?.[formData.retailer];
  const retailerBaseUrl = selectedRetailerConfig?.base_url || 'https://www.gucci.com';

  // Update product URL when retailer changes
  const handleRetailerChange = (retailer) => {
    const newRetailerConfig = retailers.retailer_configs?.[retailer];
    const newBaseUrl = newRetailerConfig?.base_url || 'https://www.gucci.com';
    
    handleInputChange('retailer', retailer);
    // Only update URL if it's still the base URL (not a specific product URL)
    if (formData.product_url === retailerBaseUrl || !formData.product_url) {
      handleInputChange('product_url', newBaseUrl);
    }
  };



  return (
    <SpaceBetween size="l">
      <Header
        variant="h1"
        description="An order automation request groups together product information, customer details, and automation settings for AI-powered e-commerce purchasing."
        actions={
          <Button
            iconName="arrow-left"
            onClick={() => navigate('/dashboard')}
          >
            Back to Dashboard
          </Button>
        }
      >
        Create order
      </Header>

      <Container header={<Header variant="h2">Order configuration</Header>}>
        <SpaceBetween size="l">
          <ColumnLayout columns={3}>
            <div style={{ gridColumn: 'span 2' }}>
              <FormField 
                label="Product name" 
                constraintText="Product name must be 1 to 255 characters. Valid characters are a-z, A-Z, 0-9, hyphens (-), and underscores (_)."
              >
                <Input
                  value={formData.product_name}
                  onChange={({ detail }) => handleInputChange('product_name', detail.value)}
                  placeholder="Enter product name"
                />
              </FormField>
            </div>
            <FormField label="Retailer">
              <Select
                selectedOption={retailerOptions.find(opt => opt.value === formData.retailer) || null}
                onChange={({ detail }) => handleRetailerChange(detail.selectedOption.value)}
                options={retailerOptions}
                placeholder="Select retailer"
              />
            </FormField>
          </ColumnLayout>

          <FormField label="Automation method" description="All methods use AgentCore Browser for secure, scalable automation">
            <Select
              selectedOption={
                formData.automation_method === 'strands_browser' 
                  ? { label: 'Strands + Browser Tools + AgentCore Browser', value: 'strands_browser' }
                  : formData.automation_method === 'nova_act'
                  ? { label: 'Nova Act + AgentCore Browser', value: 'nova_act' }
                  : { label: 'Strands + Playwright MCP + AgentCore Browser', value: 'strands_playwright_mcp' }
              }
              onChange={({ detail }) => handleInputChange('automation_method', detail.selectedOption.value)}
              options={[
                { label: 'Strands + Browser Tools + AgentCore Browser', value: 'strands_browser' },
                { label: 'Strands + Playwright MCP + AgentCore Browser', value: 'strands_playwright_mcp' },
                { label: 'Nova Act + AgentCore Browser', value: 'nova_act' }
              ]}
            />
          </FormField>

          {(formData.automation_method === 'strands_browser' || formData.automation_method === 'strands_playwright_mcp') && (
            <ModelSelector
              selectedModel={formData.ai_model}
              onChange={(model) => handleInputChange('ai_model', model)}
              label="AI Model"
              description="Bedrock model used with Strands and AgentCore Browser for web automation"
            />
          )}

          {formData.automation_method === 'nova_act' && (
            <ModelSelector
              selectedModel={formData.ai_model}
              onChange={(model) => handleInputChange('ai_model', model)}
              label="AI Model"
              description="Model used for generating Nova Act instructions. Nova Act uses its internal model with AgentCore Browser for execution."
              disabled={true}
            />
          )}
        </SpaceBetween>
      </Container>

      <ExpandableSection headerText="Product details - optional" variant="container">
        <SpaceBetween size="l">
          <Alert type="info">
            <Box>
              <strong>AI-powered detection:</strong> Leave size and color empty for automatic detection by the AI agent.
            </Box>
          </Alert>

          <FormField label="Product URL (starting URL)" constraintText="Optional - helps agent locate the product">
            <Input
              value={formData.product_url}
              onChange={({ detail }) => handleInputChange('product_url', detail.value)}
              placeholder={retailerBaseUrl}
            />
          </FormField>
          
          <ColumnLayout columns={3}>
            <FormField label="Size" constraintText="Leave empty for auto-detection">
              <Input
                value={formData.product_size}
                onChange={({ detail }) => handleInputChange('product_size', detail.value)}
                placeholder="Auto-detect"
              />
            </FormField>
            <FormField label="Color" constraintText="Leave empty for auto-detection">
              <Input
                value={formData.product_color}
                onChange={({ detail }) => handleInputChange('product_color', detail.value)}
                placeholder="Auto-detect"
              />
            </FormField>
            <FormField label="Quantity">
              <Input
                value={formData.product_quantity.toString()}
                onChange={({ detail }) => handleInputChange('product_quantity', parseInt(detail.value) || 1)}
                type="number"
                placeholder="1"
              />
            </FormField>
          </ColumnLayout>
        </SpaceBetween>
      </ExpandableSection>



      <ExpandableSection headerText="Instructions - optional" variant="container">
        <SpaceBetween size="l">
          <Alert type="info">
            <Box>
              <strong>Agent guidance:</strong> Provide specific instructions to help the AI agent make the right choices during automation.
            </Box>
          </Alert>

          <FormField 
            label="Special instructions" 
            description="Tell the agent any specific requirements or preferences"
          >
            <Textarea
              value={formData.instructions}
              onChange={({ detail }) => handleInputChange('instructions', detail.value)}
              placeholder="e.g., 'Choose the blue color if available', 'Select size Large', 'Use fastest shipping option'"
              rows={4}
            />
          </FormField>
        </SpaceBetween>
      </ExpandableSection>

      <Box float="right">
        <SpaceBetween size="m" direction="horizontal">
          <Button onClick={() => navigate('/dashboard')}>
            Cancel
          </Button>
          <Button 
            variant="primary" 
            onClick={handleSubmit}
            loading={loading}
            disabled={!validateForm()}
          >
            Create
          </Button>
        </SpaceBetween>
      </Box>
    </SpaceBetween>
  );
};

export default CreateOrder;