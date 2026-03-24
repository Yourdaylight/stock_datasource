"""Open API Gateway router — /api/open/v1/{plugin}/{method}

CRITICAL DESIGN CONSTRAINT:
    This router ONLY proxies to plugin services discovered via ServiceGenerator.
    It NEVER accesses module routers, app.routes, or any non-plugin endpoints.
"""

import json
import logging
import time
from typing import Any, Dict, List, Tuple

from fastapi import APIRouter, Depends, HTTPException, Request, status

from .dependencies import rate_limiter, require_api_key
from .schemas import EndpointInfo, EndpointListResponse, OpenApiResponse
from .service import get_open_api_service

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_plugin_service(plugin_name: str):
    """Get plugin service instance by name.

    Only returns services from plugins/*/service.py.
    """
    from stock_datasource.services.http_server import _discover_services, _get_or_create_service

    for svc_name, svc_class in _discover_services():
        if svc_name == plugin_name:
            return _get_or_create_service(svc_class, svc_name)
    return None


def _get_plugin_method(plugin_name: str, method_name: str):
    """Get a specific query method from a plugin service.

    Returns (service_instance, method_info) or (None, None).
    """
    from stock_datasource.core.service_generator import ServiceGenerator

    service = _get_plugin_service(plugin_name)
    if service is None:
        return None, None

    gen = ServiceGenerator(service)
    if method_name not in gen.methods:
        return service, None

    return service, gen.methods[method_name]


@router.post(
    "/v1/{plugin_name}/{method_name}",
    response_model=OpenApiResponse,
    summary="调用开放数据接口",
    description="通过 API Key 调用已开放的 Plugin 数据查询接口",
)
async def call_open_api(
    plugin_name: str,
    method_name: str,
    request: Request,
    auth: Tuple[dict, str] = Depends(require_api_key),
):
    """Unified open API entry point.

    Flow:
    1. API Key authentication (require_api_key dependency)
    2. Verify plugin exists in PluginManager (code-level isolation)
    3. Check access policy (is_enabled)
    4. Rate limiting
    5. Forward to plugin service method
    6. Response wrapping + usage logging
    """
    user, api_key_id = auth
    api_path = f"{plugin_name}/{method_name}"
    start_time = time.time()
    client_ip = request.client.host if request.client else ""
    open_api_svc = get_open_api_service()

    # --- 1. Verify plugin & method exist ---
    service, method_info = _get_plugin_method(plugin_name, method_name)
    if service is None:
        _log_error(open_api_svc, api_path, user, api_key_id, 404, "插件不存在", client_ip, start_time)
        raise HTTPException(status_code=404, detail=f"插件 '{plugin_name}' 不存在")
    if method_info is None:
        _log_error(open_api_svc, api_path, user, api_key_id, 404, "方法不存在", client_ip, start_time)
        raise HTTPException(status_code=404, detail=f"方法 '{method_name}' 不存在于插件 '{plugin_name}' 中")

    # --- 2. Check access policy ---
    policy = open_api_svc.get_policy(api_path)
    if not policy or not policy.get("is_enabled"):
        _log_error(open_api_svc, api_path, user, api_key_id, 403, "接口未开放", client_ip, start_time)
        raise HTTPException(status_code=403, detail=f"接口 '{api_path}' 未开放，请联系管理员")

    # --- 3. Rate limiting ---
    allowed, limit_msg = rate_limiter.check(
        api_key_id=api_key_id,
        api_path=api_path,
        limit_per_min=policy.get("rate_limit_per_min", 60),
        limit_per_day=policy.get("rate_limit_per_day", 10000),
    )
    if not allowed:
        _log_error(open_api_svc, api_path, user, api_key_id, 429, limit_msg, client_ip, start_time)
        raise HTTPException(status_code=429, detail=limit_msg)

    # --- 4. Parse request body ---
    try:
        body = await request.json()
    except Exception:
        body = {}

    # --- 5. Call plugin method ---
    try:
        method_func = method_info["method"]
        result = method_func(**body)
    except TypeError as e:
        _log_error(open_api_svc, api_path, user, api_key_id, 400, str(e), client_ip, start_time)
        raise HTTPException(status_code=400, detail=f"参数错误: {e}")
    except Exception as e:
        _log_error(open_api_svc, api_path, user, api_key_id, 500, str(e), client_ip, start_time)
        raise HTTPException(status_code=500, detail=f"查询执行失败: {e}")

    # --- 6. Response wrapping + truncation ---
    max_records = policy.get("max_records", 5000)
    record_count, truncated, data = _process_result(result, max_records)

    elapsed_ms = int((time.time() - start_time) * 1000)

    # Async usage log (fire-and-forget)
    try:
        open_api_svc.log_usage(
            api_path=api_path,
            user_id=user.get("id", ""),
            api_key_id=api_key_id,
            record_count=record_count,
            response_time_ms=elapsed_ms,
            status_code=200,
            client_ip=client_ip,
        )
    except Exception:
        pass

    return OpenApiResponse(
        status="success",
        data=data,
        record_count=record_count,
        truncated=truncated,
    )


@router.get(
    "/docs",
    response_model=EndpointListResponse,
    summary="获取已开放的接口文档",
    description="列出所有已开放的 Plugin 数据查询接口及其参数说明",
)
async def get_open_api_docs(request: Request):
    """Return documentation for all enabled open endpoints."""
    open_api_svc = get_open_api_service()
    endpoints = open_api_svc.discover_endpoints()

    # Determine base URL from request
    base_url = str(request.base_url).rstrip("/")

    result: List[EndpointInfo] = []
    for ep in endpoints:
        policy = open_api_svc.get_policy(ep["api_path"])
        is_enabled = bool(policy and policy.get("is_enabled"))
        if is_enabled:
            curl_example = _generate_curl(base_url, ep)
            result.append(EndpointInfo(
                plugin_name=ep["plugin_name"],
                method_name=ep["method_name"],
                api_path=ep["api_path"],
                description=ep.get("description", ""),
                parameters=ep.get("parameters", []),
                is_enabled=True,
                curl_example=curl_example,
            ))

    return EndpointListResponse(endpoints=result, total=len(result))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TYPE_EXAMPLE_MAP = {
    "str": "example",
    "string": "example",
    "int": 0,
    "integer": 0,
    "float": 0.0,
    "bool": True,
    "boolean": True,
}


def _generate_curl(base_url: str, ep: Dict[str, Any]) -> str:
    """Generate a sample curl command for an endpoint."""
    url = f"{base_url}/api/open/v1/{ep['api_path']}"
    body: Dict[str, Any] = {}
    for p in ep.get("parameters", []):
        name = p["name"]
        if p.get("default") is not None and p["default"] != "None":
            body[name] = p["default"]
        elif p.get("required"):
            body[name] = _TYPE_EXAMPLE_MAP.get(p.get("type", "str"), f"<{name}>")

    body_json = json.dumps(body, ensure_ascii=False, indent=2)
    curl = (
        f"curl -X POST {url} \\\n"
        f'  -H "Authorization: Bearer sk-YOUR_API_KEY" \\\n'
        f'  -H "Content-Type: application/json" \\\n'
        f"  -d '{body_json}'"
    )
    return curl


def _process_result(result: Any, max_records: int) -> tuple:
    """Process query result: count records, truncate if needed.

    Returns (record_count, truncated, processed_data).
    """
    import pandas as pd

    truncated = False

    if isinstance(result, pd.DataFrame):
        record_count = len(result)
        if record_count > max_records:
            result = result.head(max_records)
            truncated = True
            record_count = max_records
        data = result.to_dict("records")
    elif isinstance(result, list):
        record_count = len(result)
        if record_count > max_records:
            result = result[:max_records]
            truncated = True
            record_count = max_records
        data = result
    elif isinstance(result, dict):
        record_count = 1
        data = result
    elif result is None:
        record_count = 0
        data = None
    else:
        record_count = 1
        data = result

    return record_count, truncated, data


def _log_error(
    svc,
    api_path: str,
    user: dict,
    api_key_id: str,
    status_code: int,
    error_message: str,
    client_ip: str,
    start_time: float,
) -> None:
    """Log an error usage entry."""
    try:
        elapsed_ms = int((time.time() - start_time) * 1000)
        svc.log_usage(
            api_path=api_path,
            user_id=user.get("id", ""),
            api_key_id=api_key_id,
            status_code=status_code,
            error_message=error_message,
            client_ip=client_ip,
            response_time_ms=elapsed_ms,
        )
    except Exception:
        pass
