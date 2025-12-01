from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime
from enum import Enum


class OrderStatus(str, Enum):
    cart = "cart"
    pending = "pending"
    confirmed = "confirmed"
    processing = "processing"
    shipped = "shipped"
    delivered = "delivered"
    canceled = "canceled"
    
class OrderBase(BaseModel):
    user_id: Optional[str] = None
    salon_id: Optional[str] = None

    order_status: Optional[OrderStatus] = OrderStatus.cart

    subtotal: Optional[float] = 0
    tax: Optional[float] = 0
    shipping_cost: Optional[float] = 0
    total_amount: Optional[float] = 0

    shipping_address: Optional[str] = None
    notes: Optional[str] = None
    
class OrderCreateRequest(OrderBase):
    user_id: str
    salon_id: str

class OrderUpdateRequest(BaseModel):
    order_status: Optional[OrderStatus] = None
    subtotal: Optional[float] = None
    tax: Optional[float] = None
    shipping_cost: Optional[float] = None
    total_amount: Optional[float] = None
    shipping_address: Optional[str] = None
    notes: Optional[str] = None

class OrderResponse(BaseModel):
    id: str
    user_id: str
    salon_id: str
    order_status: OrderStatus
    subtotal: float
    tax: float
    shipping_cost: float
    total_amount: float
    shipping_address: Optional[str]
    notes: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    model_config = ConfigDict(from_attributes=True)
    
#--------Order Item Models--------#
class OrderItemCreateRequest(BaseModel):
    """Request model for creating an order item."""
    order_id: str
    product_id: str
    quantity: int = Field(ge=1)
    unit_price: str


class OrderItemResponse(BaseModel):
    """Response model for an order item."""
    id: str
    order_id: str
    product_id: str
    quantity: int
    unit_price: float
    subtotal: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrderItemUpdateRequest(BaseModel):
    """Request model for updating an order item."""
    quantity: Optional[int] = Field(default=None, ge=1)
    unit_price: Optional[float] = None