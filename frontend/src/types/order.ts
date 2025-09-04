/**
 * TypeScript type definitions for Order Automation System
 */

export enum OrderStatus {
  PENDING = 'pending',
  PROCESSING = 'processing',
  COMPLETED = 'completed',
  FAILED = 'failed',
  REQUIRES_HUMAN = 'requires_human'
}

export enum OrderPriority {
  LOW = 'low',
  NORMAL = 'normal',
  HIGH = 'high'
}

export interface ProductInfo {
  url: string;
  name: string;
  size: string;
  color: string;
  quantity: number;
  price?: number;
}

export interface ShippingAddress {
  first_name: string;
  last_name: string;
  address_line_1: string;
  city: string;
  state: string;
  postal_code: string;
  country: string;
  phone?: string;
}

export interface PaymentInfo {
  stripe_token: string;
  cardholder_name: string;
}

export interface OrderData {
  id?: string;
  customer_id: string;
  retailer: string;
  product: ProductInfo;
  shipping_address: ShippingAddress;
  payment_info: PaymentInfo;
  priority: OrderPriority;
  status: OrderStatus;
  created_at?: string;
  progress_percentage: number;
  current_step?: string;
  error_message?: string;
  automation_method?: string;
}

export interface BrowserSession {
  id: string;
  status: string;
  order_id?: string;
  retailer?: string;
  created_at: string;
  current_url?: string;
  thumbnail_url?: string;
}

export interface POCMetrics {
  automation_success_rate: number;
  target_success_rate: number;
  product_selection_accuracy: number;
  avg_processing_time_seconds: number;
  captcha_resolution_rate: number;
  monthly_order_capacity: number;
}

export interface RetailerConfig {
  name: string;
  base_url: string;
  supported: boolean;
  priority: number;
  poc_status: string;
  automation_methods: string[];
}

export interface POCStatus {
  phase: string;
  target_date: string;
  progress: Record<string, boolean>;
  next_milestones: Array<{
    phase: string;
    target_date: string;
    tasks: string[];
  }>;
}