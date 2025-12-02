from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from uuid import UUID
from datetime import datetime
from decimal import Decimal

#--------Product Models--------#
class ProductCreateRequest(BaseModel):
    """Request model for creating a product."""
    salon_id: str = Field(description="ID of the salon offering the product")
    category_id: Optional[str] = Field(None, description="ID of the product category")
    name: str = Field(min_length=2, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    price: str
    stock_quantity: Optional[int] = Field(None, ge=0)
    image_url: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = True
    
class ProductResponse(BaseModel):
    """Response model for a product."""
    id: str
    salon_id: str = Field(description="ID of the salon offering the product")
    category_id: Optional[str] = Field(None, description="ID of the product category")
    name: str = Field(min_length=2, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    price: float
    stock_quantity: Optional[int] = Field(None, ge=0)
    image_url: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = True
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)

class ProductUpdateRequest(BaseModel):
    """Request model for updating a product."""
    category_id: Optional[str] = Field(default=None, description="ID of the product category")
    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    price: Optional[str] = None
    stock_quantity: Optional[int] = Field(default=None, ge=0)
    image_url: Optional[str] = Field(default=None, max_length=255)
    is_active: Optional[bool] = None

#--------Product Category Models--------#
class ProductCategoryCreateRequest(BaseModel):
    """Request model for creating a product category."""
    name: str = Field(min_length=2, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    parent_category_id: Optional[str] = Field(None, description="ID of the parent product category")

class ProductCategoryResponse(BaseModel):
    """Response model for a product category."""
    id: str
    name: str
    description: Optional[str]
    parent_category_id: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)

class ProductCategoryUpdateRequest(BaseModel):
    """Request model for updating a product category."""
    id: Optional[str] = None
    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    parent_category_id: Optional[str] = Field(default=None, description="ID of the parent product category")