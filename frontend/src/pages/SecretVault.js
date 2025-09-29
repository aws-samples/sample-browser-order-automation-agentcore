import React, { useState, useEffect, useCallback } from 'react';
import {
  Header,
  SpaceBetween,
  Table,
  Button,
  ButtonDropdown,
  Modal,
  Form,
  FormField,
  Input,
  Alert,
  Box,
  TextContent
} from '@cloudscape-design/components';

const SecretVault = ({ addNotification }) => {
  const [secrets, setSecrets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedItems, setSelectedItems] = useState([]);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [editingSecret, setEditingSecret] = useState(null);
  const [formData, setFormData] = useState({
    site_name: '',
    site_url: '',
    username: '',
    password: '',
    additional_fields: {}
  });
  const [formErrors, setFormErrors] = useState({});

  const fetchSecrets = useCallback(async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/secrets');
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Failed to fetch secrets: ${response.status} ${errorText}`);
      }
      const data = await response.json();
      setSecrets(data.secrets || []);
    } catch (error) {
      console.error('Failed to fetch secrets:', error);
      setSecrets([]); // Set empty array on error to prevent infinite loading
      addNotification({
        type: 'error',
        header: 'Failed to load secrets',
        content: error.message
      });
    } finally {
      setLoading(false);
    }
  }, [addNotification]);

  useEffect(() => {
    fetchSecrets();
  }, [fetchSecrets]);

  const validateForm = () => {
    const errors = {};

    if (!formData.site_name.trim()) {
      errors.site_name = 'Site name is required';
    }

    if (!formData.site_url.trim()) {
      errors.site_url = 'Site URL is required';
    } else {
      try {
        new URL(formData.site_url);
      } catch {
        errors.site_url = 'Please enter a valid URL';
      }
    }

    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleCreate = async () => {
    if (!validateForm()) return;

    try {
      const response = await fetch('/api/secrets', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData),
      });

      if (!response.ok) {
        throw new Error('Failed to create secret');
      }

      addNotification({
        type: 'success',
        header: 'Secret created',
        content: `Secret for ${formData.site_name} has been created successfully`
      });

      setShowCreateModal(false);
      setFormData({
        site_name: '',
        site_url: '',
        username: '',
        password: '',
        additional_fields: {}
      });
      fetchSecrets();
    } catch (error) {
      addNotification({
        type: 'error',
        header: 'Failed to create secret',
        content: error.message
      });
    }
  };

  const handleEdit = async () => {
    if (!validateForm()) return;

    try {
      const response = await fetch(`/api/secrets/${editingSecret.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData),
      });

      if (!response.ok) {
        throw new Error('Failed to update secret');
      }

      addNotification({
        type: 'success',
        header: 'Secret updated',
        content: `Secret for ${formData.site_name} has been updated successfully`
      });

      setShowEditModal(false);
      setEditingSecret(null);
      fetchSecrets();
    } catch (error) {
      addNotification({
        type: 'error',
        header: 'Failed to update secret',
        content: error.message
      });
    }
  };

  const handleDelete = async () => {
    try {
      const promises = selectedItems.map(item =>
        fetch(`/api/secrets/${item.id}`, { method: 'DELETE' })
      );

      await Promise.all(promises);

      addNotification({
        type: 'success',
        header: 'Secrets deleted',
        content: `Successfully deleted ${selectedItems.length} secret(s)`
      });

      setShowDeleteModal(false);
      setSelectedItems([]);
      fetchSecrets();
    } catch (error) {
      addNotification({
        type: 'error',
        header: 'Failed to delete secrets',
        content: error.message
      });
    }
  };

  const openEditModal = (secret) => {
    setEditingSecret(secret);
    setFormData({
      site_name: secret.site_name,
      site_url: secret.site_url,
      username: secret.username || '',
      password: '', // Don't pre-fill password for security
      additional_fields: secret.additional_fields || {}
    });
    setFormErrors({});
    setShowEditModal(true);
  };

  const openCreateModal = () => {
    setFormData({
      site_name: '',
      site_url: '',
      username: '',
      password: '',
      additional_fields: {}
    });
    setFormErrors({});
    setShowCreateModal(true);
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleString();
  };

  const columnDefinitions = [
    {
      id: 'site_name',
      header: 'Site Name',
      cell: item => item.site_name,
      sortingField: 'site_name'
    },
    {
      id: 'site_url',
      header: 'Site URL',
      cell: item => (
        <a href={item.site_url} target="_blank" rel="noopener noreferrer">
          {item.site_url.length > 50 ? `${item.site_url.substring(0, 50)}...` : item.site_url}
        </a>
      )
    },
    {
      id: 'username',
      header: 'Username',
      cell: item => item.username || 'N/A'
    },
    {
      id: 'password',
      header: 'Password',
      cell: item => item.password ? '***masked***' : 'N/A'
    },
    {
      id: 'created_at',
      header: 'Created',
      cell: item => formatDate(item.created_at),
      sortingField: 'created_at'
    },
    {
      id: 'actions',
      header: 'Actions',
      cell: item => (
        <ButtonDropdown
          variant="icon"
          ariaLabel={`Actions for ${item.site_name}`}
          items={[
            {
              id: 'edit',
              text: 'Edit',
              iconName: 'edit'
            },
            {
              id: 'delete',
              text: 'Delete',
              iconName: 'remove'
            }
          ]}
          onItemClick={(e) => {
            switch (e.detail.id) {
              case 'edit':
                openEditModal(item);
                break;
              case 'delete':
                setSelectedItems([item]);
                setShowDeleteModal(true);
                break;
              default:
                break;
            }
          }}
          expandToViewport={true}
        />
      ),
      minWidth: 60
    }
  ];

  return (
    <SpaceBetween size="l">
      <Header
        variant="h1"
        description="Securely store and manage login credentials for e-commerce sites"
        actions={
          <SpaceBetween direction="horizontal" size="xs">
            <Button
              iconName="refresh"
              onClick={fetchSecrets}
              loading={loading}
            >
              Refresh
            </Button>
            <Button
              variant="primary"
              iconName="add-plus"
              onClick={openCreateModal}
            >
              Add Secret
            </Button>
          </SpaceBetween>
        }
      >
        Secret Vault
      </Header>

      <Alert type="info" header="Security Notice">
        Passwords are encrypted and stored securely. They are never displayed in plain text.
        Use this vault to store login credentials for automation agents to access e-commerce sites.
      </Alert>

      <Table
        columnDefinitions={columnDefinitions}
        items={secrets}
        loading={loading}
        selectionType="multi"
        selectedItems={selectedItems}
        onSelectionChange={({ detail }) => setSelectedItems(detail.selectedItems)}
        sortingDisabled={false}
        empty={
          <Box textAlign="center" color="inherit">
            <SpaceBetween size="m">
              <b>No secrets configured</b>
              <Button
                variant="primary"
                iconName="add-plus"
                onClick={openCreateModal}
              >
                Add your first secret
              </Button>
            </SpaceBetween>
          </Box>
        }
        header={
          <Header
            counter={`(${secrets.length})`}
            actions={
              selectedItems.length > 0 && (
                <Button
                  variant="normal"
                  iconName="remove"
                  onClick={() => setShowDeleteModal(true)}
                >
                  Delete ({selectedItems.length})
                </Button>
              )
            }
          >
            Site Credentials
          </Header>
        }
      />

      {/* Create Secret Modal */}
      <Modal
        visible={showCreateModal}
        onDismiss={() => setShowCreateModal(false)}
        header="Add New Secret"
        footer={
          <Box float="right">
            <SpaceBetween direction="horizontal" size="xs">
              <Button onClick={() => setShowCreateModal(false)}>
                Cancel
              </Button>
              <Button variant="primary" onClick={handleCreate}>
                Create Secret
              </Button>
            </SpaceBetween>
          </Box>
        }
      >
        <Form>
          <SpaceBetween size="m">
            <FormField
              label="Site Name"
              description="A friendly name for this site (e.g., 'Amazon', 'eBay')"
              errorText={formErrors.site_name}
            >
              <Input
                value={formData.site_name}
                onChange={({ detail }) => setFormData({ ...formData, site_name: detail.value })}
                placeholder="e.g., Amazon"
              />
            </FormField>

            <FormField
              label="Site URL"
              description="The base URL of the e-commerce site"
              errorText={formErrors.site_url}
            >
              <Input
                value={formData.site_url}
                onChange={({ detail }) => setFormData({ ...formData, site_url: detail.value })}
                placeholder="https://www.example.com"
              />
            </FormField>

            <FormField
              label="Username/Email"
              description="Login username or email address (optional)"
            >
              <Input
                value={formData.username}
                onChange={({ detail }) => setFormData({ ...formData, username: detail.value })}
                placeholder="user@example.com"
              />
            </FormField>

            <FormField
              label="Password"
              description="Login password (will be encrypted and stored securely)"
            >
              <Input
                type="password"
                value={formData.password}
                onChange={({ detail }) => setFormData({ ...formData, password: detail.value })}
                placeholder="Enter password"
              />
            </FormField>
          </SpaceBetween>
        </Form>
      </Modal>

      {/* Edit Secret Modal */}
      <Modal
        visible={showEditModal}
        onDismiss={() => setShowEditModal(false)}
        header={`Edit Secret - ${editingSecret?.site_name}`}
        footer={
          <Box float="right">
            <SpaceBetween direction="horizontal" size="xs">
              <Button onClick={() => setShowEditModal(false)}>
                Cancel
              </Button>
              <Button variant="primary" onClick={handleEdit}>
                Update Secret
              </Button>
            </SpaceBetween>
          </Box>
        }
      >
        <Form>
          <SpaceBetween size="m">
            <FormField
              label="Site Name"
              errorText={formErrors.site_name}
            >
              <Input
                value={formData.site_name}
                onChange={({ detail }) => setFormData({ ...formData, site_name: detail.value })}
              />
            </FormField>

            <FormField
              label="Site URL"
              errorText={formErrors.site_url}
            >
              <Input
                value={formData.site_url}
                onChange={({ detail }) => setFormData({ ...formData, site_url: detail.value })}
              />
            </FormField>

            <FormField
              label="Username/Email"
            >
              <Input
                value={formData.username}
                onChange={({ detail }) => setFormData({ ...formData, username: detail.value })}
              />
            </FormField>

            <FormField
              label="Password"
              description="Leave blank to keep existing password"
            >
              <Input
                type="password"
                value={formData.password}
                onChange={({ detail }) => setFormData({ ...formData, password: detail.value })}
                placeholder="Enter new password (optional)"
              />
            </FormField>
          </SpaceBetween>
        </Form>
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal
        visible={showDeleteModal}
        onDismiss={() => setShowDeleteModal(false)}
        header="Delete Secrets"
        footer={
          <Box float="right">
            <SpaceBetween direction="horizontal" size="xs">
              <Button onClick={() => setShowDeleteModal(false)}>
                Cancel
              </Button>
              <Button variant="primary" onClick={handleDelete}>
                Delete
              </Button>
            </SpaceBetween>
          </Box>
        }
      >
        <SpaceBetween size="m">
          <Box>
            Are you sure you want to delete {selectedItems.length} secret(s)?
          </Box>
          <Alert type="warning">
            This action cannot be undone. The selected secrets will be permanently removed.
          </Alert>
          <Box>
            <TextContent>
              <strong>Secrets to be deleted:</strong>
              <ul>
                {selectedItems.map(item => (
                  <li key={item.id}>{item.site_name} ({item.site_url})</li>
                ))}
              </ul>
            </TextContent>
          </Box>
        </SpaceBetween>
      </Modal>
    </SpaceBetween>
  );
};

export default SecretVault;