"""WeKnora Knowledge Base HTTP Client.

Lightweight async client for WeKnora REST API.
All calls are optional and fail gracefully — if WeKnora is not deployed,
the system operates without knowledge base features.
"""

import logging
import time
from typing import Optional

import httpx

from stock_datasource.config.settings import settings

logger = logging.getLogger(__name__)


class WeKnoraClient:
    """HTTP client for WeKnora knowledge base API.

    Uses a **persistent synchronous** ``httpx.Client`` for reliability.
    All public methods are sync; callers should use ``asyncio.to_thread``
    when calling from an async context if needed.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: int = 10,
        default_kb_ids: Optional[list[str]] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.default_kb_ids = default_kb_ids or []
        self._healthy: Optional[bool] = None
        self._health_checked_at: float = 0
        self._health_cache_ttl = 60
        # Persistent sync HTTP client
        self._client: Optional[httpx.Client] = None

    def _get_client(self) -> httpx.Client:
        """Return the persistent Client, creating it on first use."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(
                timeout=httpx.Timeout(
                    connect=10.0,
                    read=max(float(self.timeout), 30.0),
                    write=30.0,
                    pool=10.0,
                ),
                headers={
                    "X-API-Key": self.api_key,
                    "Content-Type": "application/json",
                },
                limits=httpx.Limits(
                    max_connections=20,
                    max_keepalive_connections=5,
                ),
                # CRITICAL: Ignore HTTP_PROXY/HTTPS_PROXY env vars set by
                # plugin extractors — WeKnora is an internal service that
                # must be accessed directly, not through the data proxy.
                trust_env=False,
            )
        return self._client

    def close(self) -> None:
        """Explicitly close the underlying HTTP client."""
        if self._client and not self._client.is_closed:
            self._client.close()
            self._client = None

    def _headers(self) -> dict:
        return {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
        }

    def _health_url(self) -> str:
        """Health endpoint is at root level, not under /api/v1."""
        # base_url is like http://host:8080/api/v1 → health is at http://host:8080/health
        base = self.base_url
        api_prefix = "/api/v1"
        if base.endswith(api_prefix):
            base = base[: -len(api_prefix)]
        elif base.endswith(api_prefix.rstrip("/")):
            base = base[: -len(api_prefix.rstrip("/"))]
        return f"{base}/health"

    def is_healthy(self, force: bool = False) -> bool:
        """Check if WeKnora service is reachable. Results are cached."""
        now = time.time()
        if not force and self._healthy is not None and (now - self._health_checked_at) < self._health_cache_ttl:
            return self._healthy

        try:
            client = self._get_client()
            resp = client.get(self._health_url(), timeout=self.timeout)
            self._healthy = resp.status_code == 200
        except Exception as e:
            logger.debug(f"[WeKnora] Health check failed: {type(e).__name__}: {e}")
            self._healthy = False

        self._health_checked_at = now
        return self._healthy

    def knowledge_search(
        self,
        query: str,
        kb_ids: Optional[list[str]] = None,
        knowledge_ids: Optional[list[str]] = None,
    ) -> list[dict]:
        """Search knowledge base, return ranked chunks with scores."""
        effective_kb_ids = kb_ids or self.default_kb_ids
        payload: dict = {"query": query}
        if effective_kb_ids:
            payload["knowledge_base_ids"] = effective_kb_ids
        if knowledge_ids:
            payload["knowledge_ids"] = knowledge_ids

        try:
            client = self._get_client()
            resp = client.post(
                f"{self.base_url}/knowledge-search",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            results = data.get("data", [])
            return results if isinstance(results, list) else []
        except Exception as e:
            logger.warning(f"[WeKnora] knowledge_search failed: {type(e).__name__}: {e}")
            return []

    def list_knowledge_bases(self) -> list[dict]:
        """List available knowledge bases."""
        try:
            client = self._get_client()
            resp = client.get(f"{self.base_url}/knowledge-bases")
            resp.raise_for_status()
            data = resp.json()
            results = data.get("data", [])
            return results if isinstance(results, list) else []
        except Exception as e:
            logger.warning(f"[WeKnora] list_knowledge_bases failed: {type(e).__name__}: {e}")
            return []

    # ------------------------------------------------------------------
    # Knowledge document CRUD
    # ------------------------------------------------------------------

    def create_manual_knowledge(
        self,
        kb_id: str,
        title: str,
        content: str,
        status: str = "publish",
    ) -> Optional[dict]:
        """Create a manual knowledge document in the specified knowledge base."""
        url = f"{self.base_url}/knowledge-bases/{kb_id}/knowledge/manual"
        content_len = len(content.encode("utf-8")) if content else 0
        read_timeout = max(60.0, float(self.timeout)) + content_len / 10240
        try:
            client = self._get_client()
            resp = client.post(
                url,
                json={"title": title, "content": content, "status": status},
                timeout=httpx.Timeout(connect=10.0, read=read_timeout, write=30.0, pool=10.0),
            )
            if resp.status_code >= 400:
                logger.warning(
                    f"[WeKnora] create_manual_knowledge HTTP {resp.status_code}: "
                    f"{resp.text[:500]}"
                )
                return None
            data = resp.json()
            return data.get("data")
        except httpx.TimeoutException:
            logger.warning(
                f"[WeKnora] create_manual_knowledge timeout after {read_timeout:.0f}s "
                f"(content_size={content_len} bytes)"
            )
            return None
        except Exception as e:
            logger.warning(f"[WeKnora] create_manual_knowledge failed: {type(e).__name__}: {e}")
            return None

    def update_manual_knowledge(
        self,
        knowledge_id: str,
        title: Optional[str] = None,
        content: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Optional[dict]:
        """Update an existing manual knowledge document."""
        payload: dict = {}
        if title is not None:
            payload["title"] = title
        if content is not None:
            payload["content"] = content
        if status is not None:
            payload["status"] = status

        if not payload:
            return None

        content_len = len(content.encode("utf-8")) if content else 0
        read_timeout = max(60.0, float(self.timeout)) + content_len / 10240
        try:
            client = self._get_client()
            resp = client.put(
                f"{self.base_url}/knowledge/manual/{knowledge_id}",
                json=payload,
                timeout=httpx.Timeout(connect=10.0, read=read_timeout, write=30.0, pool=10.0),
            )
            if resp.status_code >= 400:
                logger.warning(
                    f"[WeKnora] update_manual_knowledge({knowledge_id}) "
                    f"HTTP {resp.status_code}: {resp.text[:500]}"
                )
                return None
            data = resp.json()
            return data.get("data")
        except httpx.TimeoutException:
            logger.warning(
                f"[WeKnora] update_manual_knowledge({knowledge_id}) timeout after {read_timeout:.0f}s"
            )
            return None
        except Exception as e:
            logger.warning(
                f"[WeKnora] update_manual_knowledge({knowledge_id}) failed: "
                f"{type(e).__name__}: {e}"
            )
            return None

    def delete_knowledge(self, knowledge_id: str) -> bool:
        """Delete a knowledge document by ID."""
        try:
            client = self._get_client()
            resp = client.delete(
                f"{self.base_url}/knowledge/{knowledge_id}",
            )
            if resp.status_code >= 400:
                logger.warning(
                    f"[WeKnora] delete_knowledge({knowledge_id}) "
                    f"HTTP {resp.status_code}: {resp.text[:500]}"
                )
                return False
            return True
        except httpx.TimeoutException:
            logger.warning(f"[WeKnora] delete_knowledge({knowledge_id}) timeout")
            return False
        except Exception as e:
            logger.warning(f"[WeKnora] delete_knowledge({knowledge_id}) failed: {type(e).__name__}: {e}")
            return False

    def list_knowledges(
        self,
        kb_id: str,
        page: int = 1,
        page_size: int = 20,
        keyword: Optional[str] = None,
    ) -> dict:
        """List knowledge documents in a knowledge base."""
        params: dict = {"page": page, "page_size": page_size}
        if keyword:
            params["keyword"] = keyword

        try:
            client = self._get_client()
            resp = client.get(
                f"{self.base_url}/knowledge-bases/{kb_id}/knowledge",
                params=params,
            )
            if resp.status_code >= 400:
                logger.warning(
                    f"[WeKnora] list_knowledges({kb_id}) "
                    f"HTTP {resp.status_code}: {resp.text[:500]}"
                )
                return {"data": [], "total": 0}
            data = resp.json()
            return {
                "data": data.get("data", []),
                "total": data.get("total", 0),
            }
        except httpx.TimeoutException:
            logger.warning(f"[WeKnora] list_knowledges({kb_id}) timeout")
            return {"data": [], "total": 0}
        except Exception as e:
            logger.warning(f"[WeKnora] list_knowledges({kb_id}) failed: {type(e).__name__}: {e}")
            return {"data": [], "total": 0}

    def get_knowledge(self, knowledge_id: str) -> Optional[dict]:
        """Get a single knowledge document by ID."""
        try:
            client = self._get_client()
            resp = client.get(
                f"{self.base_url}/knowledge/{knowledge_id}",
            )
            if resp.status_code >= 400:
                logger.warning(
                    f"[WeKnora] get_knowledge({knowledge_id}) "
                    f"HTTP {resp.status_code}: {resp.text[:500]}"
                )
                return None
            data = resp.json()
            return data.get("data")
        except httpx.TimeoutException:
            logger.warning(f"[WeKnora] get_knowledge({knowledge_id}) timeout")
            return None
        except Exception as e:
            logger.warning(f"[WeKnora] get_knowledge({knowledge_id}) failed: {type(e).__name__}: {e}")
            return None

    def get_status(self) -> dict:
        """Get detailed status info for the frontend settings panel."""
        if not settings.WEKNORA_ENABLED:
            return {
                "enabled": False,
                "status": "not_configured",
                "message": "知识库服务未配置",
                "quick_deploy": _quick_deploy_info(),
            }

        healthy = self.is_healthy(force=True)
        if healthy:
            kb_count = 0
            try:
                kbs = self.list_knowledge_bases()
                kb_count = len(kbs)
            except Exception:
                pass
            return {
                "enabled": True,
                "status": "healthy",
                "message": "知识库服务已连接",
                "knowledge_bases_count": kb_count,
                "quick_deploy": None,
            }
        else:
            return {
                "enabled": True,
                "status": "unreachable",
                "message": f"知识库服务不可达: {self.base_url}",
                "quick_deploy": _quick_deploy_info(),
            }


def _quick_deploy_info() -> dict:
    """Return quick deployment instructions for the frontend guide panel."""
    return {
        "description": "WeKnora 是基于大模型的文档理解检索框架，支持 RAG 增强分析",
        "features": [
            "引用研报、公告等文档的精准分析",
            "基于公司财报数据的深度问答",
            "行业政策解读与合规信息检索",
        ],
        "steps": [
            {
                "title": "1. 启动 WeKnora 服务",
                "command": "docker-compose -f docker-compose.weknora.yml up -d",
                "note": "需要先克隆 WeKnora: git clone https://github.com/Tencent/WeKnora.git",
            },
            {
                "title": "2. 配置环境变量",
                "command": "# 在 .env 中设置:\nWEKNORA_ENABLED=true\nWEKNORA_BASE_URL=http://weknora-backend:8080/api/v1\nWEKNORA_API_KEY=your-api-key",
            },
            {
                "title": "3. 重启后端",
                "command": "docker-compose restart backend",
            },
        ],
        "docs_url": "https://weknora.weixin.qq.com",
        "github_url": "https://github.com/Tencent/WeKnora",
    }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_weknora_client: Optional[WeKnoraClient] = None


def get_weknora_client() -> Optional[WeKnoraClient]:
    """Get the global WeKnora client singleton.

    Returns None when WEKNORA_ENABLED is False or API key is missing.
    """
    global _weknora_client
    if _weknora_client is not None:
        return _weknora_client

    if not settings.WEKNORA_ENABLED:
        return None

    api_key = settings.WEKNORA_API_KEY
    if not api_key:
        logger.warning("[WeKnora] WEKNORA_ENABLED=true but WEKNORA_API_KEY is empty, skipping")
        return None

    kb_ids_str = settings.WEKNORA_KB_IDS or ""
    default_kb_ids = [k.strip() for k in kb_ids_str.split(",") if k.strip()]

    _weknora_client = WeKnoraClient(
        base_url=settings.WEKNORA_BASE_URL,
        api_key=api_key,
        timeout=settings.WEKNORA_TIMEOUT,
        default_kb_ids=default_kb_ids,
    )
    logger.info(f"[WeKnora] Client initialized: {settings.WEKNORA_BASE_URL}")
    return _weknora_client


def reset_weknora_client() -> None:
    """Reset the singleton so the next call to get_weknora_client() creates a fresh instance."""
    global _weknora_client
    _weknora_client = None
    logger.info("[WeKnora] Client singleton reset")
