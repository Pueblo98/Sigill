from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Dict, Any
from sigil.db import get_db
from sigil.models import Market, MarketPrice

router = APIRouter(prefix="/api")

@router.get("/portfolio")
async def get_portfolio(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    # Placeholder for actual portfolio accounting calculation logic
    return {
        "balance": 124500.00,
        "roi": 14.2,
        "unrealized_pnl": 12450.20,
        "realized_pnl": 2410.50
    }

@router.get("/markets")
async def get_markets(db: AsyncSession = Depends(get_db)) -> List[Dict[str, Any]]:
    # Returns active markets with their latest prices dynamically from Database
    query = select(Market).where(Market.status == "open").limit(20)
    result = await db.execute(query)
    markets = result.scalars().all()
    
    output = []
    for m in markets:
        output.append({
            "id": str(m.id),
            "platform": m.platform,
            "title": m.title,
            "resolution_date": m.resolution_date.isoformat() if m.resolution_date else None,
            "external_id": m.external_id,
            "market_type": m.market_type
        })
    return output

@router.get("/markets/{market_id}")
async def get_market(market_id: str, db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    from sqlalchemy import desc, String, cast
    from fastapi import HTTPException
    
    # We search external_id first
    m_query = await db.execute(select(Market).where(Market.external_id == market_id))
    m = m_query.scalars().first()
    
    if not m:
        # Fallback to internal UUID if needed
        m_query = await db.execute(select(Market).where(cast(Market.id, String) == market_id))
        m = m_query.scalars().first()
        if not m:
            raise HTTPException(status_code=404, detail="Market not found")

    p_query = await db.execute(
        select(MarketPrice)
        .where(MarketPrice.market_id == m.external_id)
        .order_by(desc(MarketPrice.time))
        .limit(1)
    )
    price = p_query.scalars().first()

    return {
        "id": str(m.id),
        "platform": m.platform,
        "title": m.title,
        "resolution_date": m.resolution_date.isoformat() if m.resolution_date else None,
        "external_id": m.external_id,
        "market_type": m.market_type,
        "taxonomy_l1": m.taxonomy_l1,
        "bid": price.bid if price else 0.0,
        "ask": price.ask if price else 0.0,
        "last_price": price.last_price if price else 0.0,
        "volume_24h": price.volume_24h if price else 0.0,
        "last_updated": price.time.isoformat() if price else None
    }
@router.get("/arbitrage")
async def get_arbitrage(db: AsyncSession = Depends(get_db)) -> List[Dict[str, Any]]:
    import difflib
    from sqlalchemy import select, desc
    
    # 1. Fetch active markets for both platforms
    kalshi_query = await db.execute(select(Market).where(Market.platform == 'kalshi'))
    poly_query = await db.execute(select(Market).where(Market.platform == 'polymarket'))
    
    kalshi_markets = kalshi_query.scalars().all()
    poly_markets = poly_query.scalars().all()

    # 2. Get latest prices map
    latest_prices = await db.execute(
        select(MarketPrice).order_by(desc(MarketPrice.time)).limit(500)
    )
    price_map = {p.market_id: p for p in latest_prices.scalars().all()} # simplified last-write-wins by time desc

    opportunities = []

    # 3. Fuzzy Match Option B implementation
    for k_m in kalshi_markets:
        best_match = None
        best_ratio = 0.0
        
        for p_m in poly_markets:
            ratio = difflib.SequenceMatcher(None, k_m.title.lower(), p_m.title.lower()).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = p_m
        
        # Arbitrarily pick > 0.40 since kalshi and polymarket phrase things very differently 
        if best_match and best_ratio > 0.40:
            # Look up live prices
            k_price = price_map.get(k_m.external_id)
            p_price = price_map.get(best_match.external_id)

            k_bid = (k_price.bid * 100) if k_price and k_price.bid else 50.0
            k_ask = (k_price.ask * 100) if k_price and k_price.ask else 52.0
            p_bid = (p_price.bid * 100) if p_price and p_price.bid else 48.0
            p_ask = (p_price.ask * 100) if p_price and p_price.ask else 50.0

            opportunities.append({
                "event": k_m.title,
                "kalshi_ticker": k_m.external_id[:12],
                "poly_ticker": best_match.external_id[:12],
                "kalshi_bid": k_bid,
                "kalshi_ask": k_ask,
                "kalshi_min_size": 1000,
                "poly_bid": p_bid,
                "poly_ask": p_ask,
                "poly_min_size": 1000,
                "implied_sum": k_bid + p_ask, # Simple implied sum logic
                "net_arb": max(0, 100 - (k_bid + p_ask)) # Mock logic for structural demo
            })

    # Fallback to structural demo if DB is completely missing overlap
    if not opportunities:
        return []
        
    return opportunities
