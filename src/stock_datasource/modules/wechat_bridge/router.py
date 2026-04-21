"""WeChat Bridge API routes - picoclash integration."""

import logging
import subprocess

from fastapi import APIRouter, Depends, HTTPException

from ..auth.dependencies import get_current_user, require_admin
from .schemas import ActionResponse, PicoclawStatus
from .service import (
    generate_config,
    get_config_preview,
    get_status,
    start_bridge,
    stop_bridge,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["微信联动"])


@router.get("/status", response_model=PicoclawStatus)
def get_picoclaw_status(current_user: dict = Depends(get_current_user)):
    """Get picoclaw and wechat bridge status."""
    return get_status()


@router.get("/config")
def get_config_status(current_user: dict = Depends(get_current_user)):
    """Get current picoclaw config preview."""
    return get_config_preview()


@router.post("/generate-config", response_model=ActionResponse)
def api_generate_config(
    mcp_token: str | None = None,
    _admin: dict = Depends(require_admin),
):
    """Generate (or regenerate) picoclaw config from .env."""
    try:
        result = generate_config(mcp_token=mcp_token)
        return ActionResponse(
            success=True, message=f"配置已生成: {result['config_path']}"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成配置失败: {e}")


@router.post("/start", response_model=ActionResponse)
def api_start_bridge(
    mcp_token: str | None = None,
    symbols: str | None = None,
    no_rt: bool = False,
    _admin: dict = Depends(require_admin),
):
    """Start picoclaw gateway + wechat channel + realtime subscription."""
    try:
        result = start_bridge(symbols=symbols, no_rt=no_rt)
        return ActionResponse(**result)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to start bridge: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"启动失败: {e}")


@router.post("/stop", response_model=ActionResponse)
def api_stop_bridge(_admin: dict = Depends(require_admin)):
    """Stop all picoclaw-related processes."""
    try:
        result = stop_bridge()
        return ActionResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"停止失败: {e}")


@router.get("/weixin-qr")
def get_wechat_qr(_admin: dict = Depends(require_admin)):
    """Trigger WeChat QR code login and return QR code link for frontend rendering."""
    import os
    import re

    from .service import BIN_DIR, PICOCLAW_BIN, PROJECT_ROOT

    status = get_status()
    if not status["installed"]:
        raise HTTPException(status_code=404, detail="PicoClaw 未安装")

    env = os.environ.copy()
    env["PATH"] = str(BIN_DIR) + ":" + env.get("PATH", "")

    try:
        proc = subprocess.Popen(
            [str(PICOCLAW_BIN), "auth", "weixin"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
            cwd=str(PROJECT_ROOT),
        )

        # Read output until we find the QR Code Link (max 15s)
        import time as _time

        output_lines = []
        qr_url = None
        deadline = _time.monotonic() + 15

        while _time.monotonic() < deadline:
            line = proc.stdout.readline()
            if not line:
                if proc.poll() is not None:
                    break
                _time.sleep(0.1)
                continue
            output_lines.append(line.rstrip())
            # Look for QR Code Link
            m = re.search(r"QR Code Link:\s*(https?://\S+)", line)
            if m:
                qr_url = m.group(1)
                break

        if not qr_url:
            # Process may have failed or timed out
            try:
                proc.terminate()
            except Exception:
                pass
            return {
                "success": False,
                "message": "未能获取二维码链接",
                "qr_url": None,
                "output": "\n".join(output_lines[-10:]),
                "pid": proc.pid,
            }

        return {
            "success": True,
            "message": "请使用微信扫描二维码登录",
            "qr_url": qr_url,
            "output": None,
            "pid": proc.pid,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"触发微信登录失败: {e}")
