from typing import Protocol, List, Optional, AsyncIterator
from datetime import datetime
from pydantic import BaseModel
from uuid import UUID

class Balance(BaseModel):
    available: float
    total: float
    currency: str = "USD"

class ExchangeAdapter(Protocol):
    async def get_balance(self) -> Balance: ...
    
    async def place_order(
        self, 
        market_external_id: str, 
        side: str, 
        outcome: str, 
        price: float, 
        quantity: int,
        order_type: str = "limit"
    ) -> str: 
        """Returns external_order_id"""
        ...
        
    async def cancel_order(self, external_order_id: str) -> bool: ...
    
    async def get_order_status(self, external_order_id: str) -> str: ...
    
    async def sync_positions(self) -> List[dict]: ...
