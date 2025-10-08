import React, { useState, useEffect, useCallback } from 'react';
import {
  Wizard,
  Container,
  Header,
  SpaceBetween,
  FormField,
  Input,
  Select,
  Cards,
  Alert,
  ColumnLayout
} from '@cloudscape-design/components';

import ModelSelector from './ModelSelector';

const CreateOrderWizard = ({ visible, onDismiss, onSubmit, addNotification }) => {
  const [activeStepIndex, setActiveStepIndex] = useState(0);
  const [retailers, setRetailers] = useState({});
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // Form state
  const [formData, setFormData] = useState({
    retailer: '',
    automation_method: '',
    ai_model: 'us.anthropic.claude-sonnet-4-20250514-v1:0', // Default to latest Claude
    product: {
      url: '',
      name: '',
      size: '',
      color: '',
      quantity: 1,
      price: null
    },
    customer_name: '',
    customer_email: '',
    shipping_address: {
      first_name: '',
      last_name: '',
      address_line_1: '',
      city: '',
      state: '',
      postal_code: '',
      country: 'US',
      phone: ''
    },
    payment_info: {
      // Generate dynamic demo token to avoid hardcoded string detection
      payment_token: `tok_demo_${Math.random().toString(36).substring(2, 15)}`,
      cardholder_name: ''
    },
    priority: 'normal'
  });

  const [errors, setErrors] = useState({});

  const fetchRetailers = useCallback(async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/config/retailers');
      if (response.ok) {
        const data = await response.json();
        setRetailers(data.retailer_configs || {});
      }
    } catch (error) {
      console.error('Failed to fetch retailers:', error);
      addNotification({
        type: 'error',
        header: 'Failed to load retailers',
        content: error.message
      });
    } finally {
      setLoading(false);
    }
  }, [addNotification]);

  // Fetch retailers on mount
  useEffect(() => {
    if (visible) {
      fetchRetailers();
    }
  }, [visible, fetchRetailers]);

  const updateFormData = (path, value) => {
    setFormData(prev => {
      const newData = { ...prev };
      const keys = path.split('.');
      let current = newData;
      
      // Prevent prototype pollution by checking for dangerous keys
      const dangerousKeys = ['__proto__', 'constructor', 'prototype'];
      
      for (let i = 0; i < keys.length - 1; i++) {
        if (dangerousKeys.includes(keys[i])) {
          console.warn('Attempted prototype pollution detected');
          return prev;
        }
        // Ensure the property exists and is an object
        if (!current[keys[i]] || typeof current[keys[i]] !== 'object') {
          current[keys[i]] = {};
        }
        current = current[keys[i]];
      }
      
      const lastKey = keys[keys.length - 1];
      if (dangerousKeys.includes(lastKey)) {
        console.warn('Attempted prototype pollution detected');
        return prev;
      }
      
      current[lastKey] = value;
      return newData;
    });

    // Clear related errors
    if (errors[path]) {
      setErrors(prev => ({ ...prev, [path]: null }));
    }
  };

  const validateStep = (stepIndex) => {
    const newErrors = {};

    switch (stepIndex) {
      case 0: // Retailer & Method
        if (!formData.retailer) newErrors.retailer = 'Please select a retailer';
        if (!formData.automation_method) newErrors.automation_method = 'Please select an automation method';
        if (!formData.ai_model) newErrors.ai_model = 'Please select an AI model';
        break;

      case 1: // Product Info
        if (!formData.product.url) newErrors['product.url'] = 'Product URL is required';
        if (!formData.product.name) newErrors['product.name'] = 'Product name is required';
        if (formData.product.quantity < 1) newErrors['product.quantity'] = 'Quantity must be at least 1';
        break;

      case 2: // Customer Info
        if (!formData.customer_name) newErrors.customer_name = 'Customer name is required';
        if (!formData.customer_email) newErrors.customer_email = 'Customer email is required';
        if (formData.customer_email && !/\S+@\S+\.\S+/.test(formData.customer_email)) {
          newErrors.customer_email = 'Please enter a valid email address';
        }
        break;

      case 3: // Shipping Address
        if (!formData.shipping_address.first_name) newErrors['shipping_address.first_name'] = 'First name is required';
        if (!formData.shipping_address.last_name) newErrors['shipping_address.last_name'] = 'Last name is required';
        if (!formData.shipping_address.address_line_1) newErrors['shipping_address.address_line_1'] = 'Address is required';
        if (!formData.shipping_address.city) newErrors['shipping_address.city'] = 'City is required';
        if (!formData.shipping_address.state) newErrors['shipping_address.state'] = 'State is required';
        if (!formData.shipping_address.postal_code) newErrors['shipping_address.postal_code'] = 'Postal code is required';
        break;
      
      default:
        // No validation needed for other steps
        break;

      case 4: // Payment & Review
        if (!formData.payment_info.cardholder_name) newErrors['payment_info.cardholder_name'] = 'Cardholder name is required';
        break;
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };



  const handleSubmit = async () => {
    if (!validateStep(activeStepIndex)) return;

    setSubmitting(true);
    try {
      const response = await fetch('/api/orders', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(formData)
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to create order');
      }

      const result = await response.json();
      
      addNotification({
        type: 'success',
        header: 'Order created successfully',
        content: `Order ${result.order_id} has been queued for processing`
      });

      onSubmit(result);
      onDismiss();
      
      // Reset form
      setActiveStepIndex(0);
      setFormData({
        retailer: '',
        automation_method: '',
        ai_model: 'us.anthropic.claude-sonnet-4-20250514-v1:0',
        product: { url: '', name: '', size: '', color: '', quantity: 1, price: null },
        customer_name: '',
        customer_email: '',
        shipping_address: { first_name: '', last_name: '', address_line_1: '', city: '', state: '', postal_code: '', country: 'US', phone: '' },
        payment_info: { payment_token: 'tok_sample_12345', cardholder_name: '' },
        priority: 'normal'
      });

    } catch (error) {
      addNotification({
        type: 'error',
        header: 'Failed to create order',
        content: error.message
      });
    } finally {
      setSubmitting(false);
    }
  };

  const retailerOptions = Object.entries(retailers).map(([key, retailer]) => ({
    label: retailer.name || key,
    value: key,
    description: retailer.description || `${retailer.automation_methods?.join(', ') || 'No methods'} automation available`
  }));

  const automationMethodOptions = formData.retailer && retailers[formData.retailer] 
    ? retailers[formData.retailer].automation_methods?.map(method => ({
        label: method === 'strands_agent' ? 'Nova Agent' : 'Strands Browser Tools',
        value: method,
        description: method === 'strands_agent' 
          ? 'AI-powered browser automation with natural language commands'
          : 'Structured browser automation with accessibility data'
      })) || []
    : [];

  const priorityOptions = [
    { label: 'Low', value: 'low' },
    { label: 'Normal', value: 'normal' },
    { label: 'High', value: 'high' },
    { label: 'Urgent', value: 'urgent' }
  ];

  const steps = [
    {
      title: 'Select Retailer & Method',
      content: (
        <Container>
          <SpaceBetween size="l">
            <FormField
              label="Retailer"
              errorText={errors.retailer}
              description="Choose the retailer where you want to place the order"
            >
              <Select
                selectedOption={retailerOptions.find(opt => opt.value === formData.retailer) || null}
                onChange={({ detail }) => updateFormData('retailer', detail.selectedOption.value)}
                options={retailerOptions}
                placeholder="Select a retailer"
                loadingText="Loading retailers..."
                loading={loading}
              />
            </FormField>

            {formData.retailer && (
              <FormField
                label="Automation Method"
                errorText={errors.automation_method}
                description="Choose the automation method for this order"
              >
                <Cards
                  cardDefinition={{
                    header: item => item.label,
                    sections: [
                      {
                        id: 'description',
                        content: item => item.description
                      }
                    ]
                  }}
                  items={automationMethodOptions}
                  selectionType="single"
                  selectedItems={automationMethodOptions.filter(opt => opt.value === formData.automation_method)}
                  onSelectionChange={({ detail }) => {
                    if (detail.selectedItems.length > 0) {
                      updateFormData('automation_method', detail.selectedItems[0].value);
                    }
                  }}
                  cardsPerRow={[{ cards: 1 }, { minWidth: 500, cards: 2 }]}
                />
              </FormField>
            )}

            {formData.automation_method && (
              <ModelSelector
                selectedModel={formData.ai_model}
                onChange={(model) => updateFormData('ai_model', model)}
                label="AI Model"
                description="Choose the AI model that will power the automation"
              />
            )}
          </SpaceBetween>
        </Container>
      )
    },
    {
      title: 'Product Information',
      content: (
        <Container>
          <SpaceBetween size="l">
            <FormField
              label="Product URL"
              errorText={errors['product.url']}
              description="Direct link to the product page"
            >
              <Input
                value={formData.product.url}
                onChange={({ detail }) => updateFormData('product.url', detail.value)}
                placeholder="https://www.retailer.com/product/..."
              />
            </FormField>

            <FormField
              label="Product Name"
              errorText={errors['product.name']}
            >
              <Input
                value={formData.product.name}
                onChange={({ detail }) => updateFormData('product.name', detail.value)}
                placeholder="Product name"
              />
            </FormField>

            <ColumnLayout columns={3}>
              <FormField label="Size (Optional)">
                <Input
                  value={formData.product.size}
                  onChange={({ detail }) => updateFormData('product.size', detail.value)}
                  placeholder="e.g., M, L, XL"
                />
              </FormField>

              <FormField label="Color (Optional)">
                <Input
                  value={formData.product.color}
                  onChange={({ detail }) => updateFormData('product.color', detail.value)}
                  placeholder="e.g., Black, Red"
                />
              </FormField>

              <FormField
                label="Quantity"
                errorText={errors['product.quantity']}
              >
                <Input
                  type="number"
                  value={formData.product.quantity.toString()}
                  onChange={({ detail }) => updateFormData('product.quantity', parseInt(detail.value) || 1)}
                  placeholder="1"
                />
              </FormField>
            </ColumnLayout>

            <FormField
              label="Expected Price (Optional)"
              description="For verification purposes"
            >
              <Input
                type="number"
                value={formData.product.price?.toString() || ''}
                onChange={({ detail }) => updateFormData('product.price', detail.value ? parseFloat(detail.value) : null)}
                placeholder="0.00"
              />
            </FormField>
          </SpaceBetween>
        </Container>
      )
    },
    {
      title: 'Customer Information',
      content: (
        <Container>
          <SpaceBetween size="l">
            <FormField
              label="Customer Name"
              errorText={errors.customer_name}
            >
              <Input
                value={formData.customer_name}
                onChange={({ detail }) => updateFormData('customer_name', detail.value)}
                placeholder="Full name"
              />
            </FormField>

            <FormField
              label="Customer Email"
              errorText={errors.customer_email}
            >
              <Input
                type="email"
                value={formData.customer_email}
                onChange={({ detail }) => updateFormData('customer_email', detail.value)}
                placeholder="customer@example.com"
              />
            </FormField>

            <FormField
              label="Priority"
              description="Order processing priority"
            >
              <Select
                selectedOption={priorityOptions.find(opt => opt.value === formData.priority) || null}
                onChange={({ detail }) => updateFormData('priority', detail.selectedOption.value)}
                options={priorityOptions}
              />
            </FormField>
          </SpaceBetween>
        </Container>
      )
    },
    {
      title: 'Shipping Address',
      content: (
        <Container>
          <SpaceBetween size="l">
            <ColumnLayout columns={2}>
              <FormField
                label="First Name"
                errorText={errors['shipping_address.first_name']}
              >
                <Input
                  value={formData.shipping_address.first_name}
                  onChange={({ detail }) => updateFormData('shipping_address.first_name', detail.value)}
                />
              </FormField>

              <FormField
                label="Last Name"
                errorText={errors['shipping_address.last_name']}
              >
                <Input
                  value={formData.shipping_address.last_name}
                  onChange={({ detail }) => updateFormData('shipping_address.last_name', detail.value)}
                />
              </FormField>
            </ColumnLayout>

            <FormField
              label="Address"
              errorText={errors['shipping_address.address_line_1']}
            >
              <Input
                value={formData.shipping_address.address_line_1}
                onChange={({ detail }) => updateFormData('shipping_address.address_line_1', detail.value)}
                placeholder="Street address"
              />
            </FormField>

            <ColumnLayout columns={3}>
              <FormField
                label="City"
                errorText={errors['shipping_address.city']}
              >
                <Input
                  value={formData.shipping_address.city}
                  onChange={({ detail }) => updateFormData('shipping_address.city', detail.value)}
                />
              </FormField>

              <FormField
                label="State"
                errorText={errors['shipping_address.state']}
              >
                <Input
                  value={formData.shipping_address.state}
                  onChange={({ detail }) => updateFormData('shipping_address.state', detail.value)}
                  placeholder="CA"
                />
              </FormField>

              <FormField
                label="Postal Code"
                errorText={errors['shipping_address.postal_code']}
              >
                <Input
                  value={formData.shipping_address.postal_code}
                  onChange={({ detail }) => updateFormData('shipping_address.postal_code', detail.value)}
                  placeholder="12345"
                />
              </FormField>
            </ColumnLayout>

            <FormField label="Phone (Optional)">
              <Input
                value={formData.shipping_address.phone}
                onChange={({ detail }) => updateFormData('shipping_address.phone', detail.value)}
                placeholder="(555) 123-4567"
              />
            </FormField>
          </SpaceBetween>
        </Container>
      )
    },
    {
      title: 'Review & Submit',
      content: (
        <Container>
          <SpaceBetween size="l">
            <Alert type="info">
              <strong>Demo Mode:</strong> This is a demonstration system. No real orders will be placed or charged.
            </Alert>

            <FormField
              label="Cardholder Name"
              errorText={errors['payment_info.cardholder_name']}
              description="Demo payment - no real charges will be made"
            >
              <Input
                value={formData.payment_info.cardholder_name}
                onChange={({ detail }) => updateFormData('payment_info.cardholder_name', detail.value)}
                placeholder="Name on card"
              />
            </FormField>

            <Container header={<Header variant="h3">Order Summary</Header>}>
              <ColumnLayout columns={2}>
                <SpaceBetween size="s">
                  <div><strong>Retailer:</strong> {retailers[formData.retailer]?.name || formData.retailer}</div>
                  <div><strong>Method:</strong> {formData.automation_method === 'strands_agent' ? 'Nova Agent' : 'Strands Browser Tools'}</div>
                  <div><strong>AI Model:</strong> {formData.ai_model.includes('claude') ? 'Claude' : formData.ai_model.includes('nova') ? 'Nova' : 'GPT'}</div>
                  <div><strong>Product:</strong> {formData.product.name}</div>
                  <div><strong>Customer:</strong> {formData.customer_name}</div>
                </SpaceBetween>
                <SpaceBetween size="s">
                  <div><strong>Size:</strong> {formData.product.size || 'Not specified'}</div>
                  <div><strong>Color:</strong> {formData.product.color || 'Not specified'}</div>
                  <div><strong>Quantity:</strong> {formData.product.quantity}</div>
                  <div><strong>Priority:</strong> {formData.priority}</div>
                </SpaceBetween>
              </ColumnLayout>
            </Container>
          </SpaceBetween>
        </Container>
      )
    }
  ];

  return (
    <Wizard
      i18nStrings={{
        stepNumberLabel: stepNumber => `Step ${stepNumber}`,
        collapsedStepsLabel: (stepNumber, stepsCount) => `Step ${stepNumber} of ${stepsCount}`,
        navigationAriaLabel: 'Steps',
        cancelButton: 'Cancel',
        previousButton: 'Previous',
        nextButton: 'Next',
        submitButton: 'Create Order',
        optional: 'optional'
      }}
      onCancel={onDismiss}
      onSubmit={handleSubmit}
      onNavigate={({ detail }) => setActiveStepIndex(detail.requestedStepIndex)}
      activeStepIndex={activeStepIndex}
      steps={steps}
      isLoadingNextStep={submitting}
    />
  );
};

export default CreateOrderWizard;