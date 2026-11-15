import type { components } from './api'

export type Schemas = components['schemas']
export type SessionData = Schemas['SessionData']
export type HealthData = Schemas['HealthData']
export type UserSummary = Schemas['UserSummary']
export type Address = Schemas['Address']
export type Category = Schemas['CategoryData']
export type Product = Schemas['ProductOutput']
export type Sku = Schemas['SkuOutput']
export type CartItem = Schemas['Item']
export type CartData = Schemas['CartData']
export type QuoteLine = Schemas['QuoteLine']
export type QuoteData = Schemas['QuoteData']
export type OrderSummary = Schemas['OrderSummary']
export type OrderDetail = Schemas['OrderDetailData']
export type Coupon = Schemas['CouponData']
export type ReviewRow = Schemas['OpsRow']
export type Notice = Schemas['Notice']
export type NotificationTemplate = Schemas['NotificationTemplateData']
export type Conversation = Schemas['ConversationData']
export type ChatMessage = Schemas['MessageData']
export type SupportHistory = Schemas['HistoryData']
export type Content = Schemas['ContentData']
export type Revision = Schemas['RevisionData']
export type PublicContent = Schemas['PublicContentData']
export type RoleUser = Schemas['RoleUserData']
export type RoleOption = Schemas['RoleOption']
export type AuditRow = Schemas['AuditData']
export type TemplateData = Schemas['TemplateData']
export type Unread = Schemas['Unread']
export type ReadResult = Schemas['ReadResult']
export type NoticePage = Schemas['NoticePage']
export type PublicReviewPage = Schemas['PublicPage']

export interface Page<T> {
  count: number
  page: number
  page_size: number
  total_pages: number
  results: T[]
}

export interface GuestCartLine {
  sku_id: string
  title: string
  label: string
  current_price: string
  quantity: number
}

export interface GuestCartBatch {
  owner: string
  key: string
  items: { sku_id: string; quantity: number }[]
}

export interface GuestCart {
  items: GuestCartLine[]
  batch: GuestCartBatch | null
  needsConfirmation: boolean
}

export interface PendingLine {
  sku_id: string
  title: string
  label: string
  current_price: string
  quantity: number
  reason?: string
}

export interface PendingMessage {
  client_message_id: string
  body: string
  state: 'sending' | 'failed' | 'retrying'
  retryable: boolean
}

export type ApiError = Error & {
  code?: number
  response?: { status: number; data?: { code?: number; message?: string } }
  body?: { code?: number; message?: string }
}
