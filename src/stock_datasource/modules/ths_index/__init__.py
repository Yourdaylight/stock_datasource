"""THS (TongHuaShun) Sector Index module.

Provides API endpoints for THS sector index data including:
- Sector index list (industry, concept, region, etc.)
- Sector daily data
- Sector ranking by various metrics
"""

from .router import router
from .service import get_ths_index_service, THSIndexService

__all__ = ["router", "get_ths_index_service", "THSIndexService"]
