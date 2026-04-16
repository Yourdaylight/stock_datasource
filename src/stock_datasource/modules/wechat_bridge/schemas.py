"""Schemas for WeChat Bridge (picoclaw) integration."""

from pydantic import BaseModel


class PicoclawStatus(BaseModel):
    """Picoclaw process status."""

    installed: bool = False
    version: str | None = None
    running: bool = False
    pid: int | None = None
    port: int | None = None
    gateway_url: str | None = None
    rt_running: bool = False
    rt_pid: int | None = None
    config_exists: bool = False
    config_path: str = ""


class WechatLoginStatus(BaseModel):
    """WeChat login status via picoclaw."""

    logged_in: bool = False
    nickname: str | None = None
    login_qr_code: str | None = None  # base64 encoded QR image or URL


class PicoclawConfig(BaseModel):
    """Picoclaw configuration preview."""

    llm_model: str = ""
    llm_base_url: str = ""
    mcp_server_url: str = ""
    mcp_connected: bool = False
    ws_realtime_url: str = ""
    channel_weixin_enabled: bool = False
    config_path: str = ""


class StartRequest(BaseModel):
    """Request to start picoclaw bridge."""

    mcp_token: str | None = None
    symbols: str | None = None  # comma-separated stock symbols
    no_rt: bool = False
    port: int = 18790


class ActionResponse(BaseModel):
    """Generic action response."""

    success: bool
    message: str
    pid: int | None = None
    rt_pid: int | None = None
