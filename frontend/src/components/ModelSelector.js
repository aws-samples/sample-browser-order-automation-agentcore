import React from 'react';
import {
  FormField,
  Select
} from '@cloudscape-design/components';

const ModelSelector = ({ selectedModel, onChange, label = "AI Model", description, disabled = false }) => {
  const models = [
    {
      id: 'us.anthropic.claude-sonnet-4-20250514-v1:0',
      name: 'Claude Sonnet 4'
    },
    {
      id: 'us.anthropic.claude-3-7-sonnet-20250219-v1:0',
      name: 'Claude 3.7 Sonnet'
    },
    {
      id: 'us.amazon.nova-pro-v1:0',
      name: 'Amazon Nova Pro'
    },
    {
      id: 'openai.gpt-oss-120b-1:0',
      name: 'GPT-OSS 120B'
    },
    {
      id: 'openai.gpt-oss-20b-1:0',
      name: 'GPT-OSS 20B'
    },
    {
      id: 'deepseek.v3-v1:0',
      name: 'DeepSeek V3'
    },
    {
      id: 'nova_act',
      name: 'Nova Act'
    }
  ];

  const selectOptions = models.map(model => ({
    label: model.name,
    value: model.id
  }));

  return (
    <FormField
      label={label}
      description={description}
    >
      <Select
        selectedOption={selectOptions.find(opt => opt.value === selectedModel) || null}
        onChange={({ detail }) => onChange(detail.selectedOption.value)}
        options={selectOptions}
        placeholder="Select an AI model"
        disabled={disabled}
        expandToViewport
      />
    </FormField>
  );
};

export default ModelSelector;