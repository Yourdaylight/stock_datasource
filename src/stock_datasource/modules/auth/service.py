"""Authentication service with JWT token and password hashing."""

import os
import uuid
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from pathlib import Path

import jwt
from passlib.context import CryptContext

from stock_datasource.models.database import db_client

logger = logging.getLogger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "stock-datasource-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_DAYS = 7


class AuthService:
    """Authentication service for user management."""
    
    def __init__(self):
        self.client = db_client
        self._tables_initialized = False
    
    def _ensure_tables(self) -> None:
        """Ensure auth tables exist (lazy initialization)."""
        if self._tables_initialized:
            return
        
        schema_file = Path(__file__).parent / "schema.sql"
        if schema_file.exists():
            sql_content = schema_file.read_text()
            for statement in sql_content.split(";"):
                statement = statement.strip()
                if statement:
                    try:
                        self.client.execute(statement)
                    except Exception as e:
                        logger.warning(f"Failed to execute schema statement: {e}")
        
        self._tables_initialized = True
    
    def hash_password(self, password: str) -> str:
        """Hash a password using bcrypt."""
        return pwd_context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return pwd_context.verify(plain_password, hashed_password)
    
    def create_access_token(self, user_id: str, email: str) -> tuple[str, int]:
        """Create a JWT access token.
        
        Returns:
            Tuple of (token, expires_in_seconds)
        """
        expires_delta = timedelta(days=JWT_EXPIRATION_DAYS)
        expire = datetime.now(timezone.utc) + expires_delta
        
        payload = {
            "sub": user_id,
            "email": email,
            "exp": expire,
            "iat": datetime.now(timezone.utc),
        }
        
        token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
        expires_in = int(expires_delta.total_seconds())
        
        return token, expires_in
    
    def decode_token(self, token: str) -> Optional[dict]:
        """Decode and validate a JWT token.
        
        Returns:
            Token payload if valid, None otherwise
        """
        try:
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            logger.debug("Token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.debug(f"Invalid token: {e}")
            return None
    
    def is_email_whitelisted(self, email: str) -> bool:
        """Check if email is in the whitelist."""
        self._ensure_tables()
        query = """
            SELECT count() as cnt
            FROM email_whitelist FINAL
            WHERE email = %(email)s AND is_active = 1
        """
        result = self.client.execute(query, {"email": email.lower()})
        return result[0][0] > 0 if result else False
    
    def get_user_by_email(self, email: str) -> Optional[dict]:
        """Get user by email."""
        self._ensure_tables()
        query = """
            SELECT id, email, username, password_hash, is_active, created_at, updated_at
            FROM users FINAL
            WHERE email = %(email)s AND is_active = 1
            LIMIT 1
        """
        result = self.client.execute(query, {"email": email.lower()})
        if result:
            row = result[0]
            return {
                "id": row[0],
                "email": row[1],
                "username": row[2],
                "password_hash": row[3],
                "is_active": bool(row[4]),
                "created_at": row[5],
                "updated_at": row[6],
            }
        return None
    
    def get_user_by_id(self, user_id: str) -> Optional[dict]:
        """Get user by ID."""
        self._ensure_tables()
        query = """
            SELECT id, email, username, password_hash, is_active, created_at, updated_at
            FROM users FINAL
            WHERE id = %(user_id)s AND is_active = 1
            LIMIT 1
        """
        result = self.client.execute(query, {"user_id": user_id})
        if result:
            row = result[0]
            return {
                "id": row[0],
                "email": row[1],
                "username": row[2],
                "password_hash": row[3],
                "is_active": bool(row[4]),
                "created_at": row[5],
                "updated_at": row[6],
            }
        return None
    
    def _resolve_whitelist_file(self) -> Optional[Path]:
        """Resolve whitelist file path from settings.

        Compatibility notes:
        - Some older deployments may not have whitelist fields in Settings.
        - Relative paths are resolved from current working directory (docker: /app).
        """
        from stock_datasource.config.settings import settings

        file_path = getattr(settings, "AUTH_EMAIL_WHITELIST_FILE", None)
        if not file_path:
            return None

        path = Path(str(file_path))
        if not path.is_absolute():
            path = Path.cwd() / path

        if path.exists():
            return path

        # Fallbacks for historical conventions
        candidates = [
            Path.cwd() / "email.txt",
            Path.cwd() / "data" / "email.txt",
        ]
        for cand in candidates:
            if cand.exists():
                return cand

        return None

    def _is_email_in_whitelist_file(self, email: str) -> bool:
        """Check whitelist file (email.txt) for an email address.

        Supports both semicolon-separated and newline-separated formats.
        """
        path = self._resolve_whitelist_file()
        if not path:
            return False

        try:
            content = path.read_text(encoding="utf-8").strip()
        except Exception as e:
            logger.warning(f"Failed to read whitelist file {path}: {e}")
            return False

        if not content:
            return False

        if ";" in content:
            emails = {e.strip().lower() for e in content.split(";") if e.strip()}
        else:
            emails = {e.strip().lower() for e in content.split("\n") if e.strip()}

        return email.lower() in emails

    def is_email_allowed_for_registration(self, email: str) -> bool:
        """Check if email is allowed for registration.

        - If whitelist is disabled, allow all.
        - If whitelist is enabled, allow if either:
          1) present in DB whitelist, or
          2) present in whitelist file (email.txt).

        The file check makes whitelist effective immediately without requiring an import step.
        """
        from stock_datasource.config.settings import settings

        whitelist_enabled = bool(getattr(settings, "AUTH_EMAIL_WHITELIST_ENABLED", False))
        if not whitelist_enabled:
            return True

        # Prefer DB whitelist (supports UI management)
        try:
            if self.is_email_whitelisted(email):
                return True
        except Exception as e:
            logger.warning(f"DB whitelist check failed, fallback to file: {e}")

        if self._is_email_in_whitelist_file(email):
            # Best-effort: sync into DB for future reads
            try:
                self.add_email_to_whitelist(email, added_by="file")
            except Exception:
                pass
            return True

        return False

    def register_user(self, email: str, password: str, username: Optional[str] = None) -> tuple[bool, str, Optional[dict]]:
        """Register a new user.
        
        Returns:
            Tuple of (success, message, user_dict)
        """
        email = email.lower()

        # Check whitelist (configurable)
        if not self.is_email_allowed_for_registration(email):
            return False, "该邮箱不在允许注册的范围内", None
        
        # Check if email already registered
        existing_user = self.get_user_by_email(email)
        if existing_user:
            return False, "该邮箱已被注册", None
        
        # Create user
        user_id = str(uuid.uuid4())
        if not username:
            username = email.split("@")[0]
        
        password_hash = self.hash_password(password)
        now = datetime.now()
        
        insert_query = """
            INSERT INTO users (id, email, username, password_hash, is_active, created_at, updated_at)
            VALUES (%(id)s, %(email)s, %(username)s, %(password_hash)s, 1, %(created_at)s, %(updated_at)s)
        """
        
        try:
            self.client.execute(insert_query, {
                "id": user_id,
                "email": email,
                "username": username,
                "password_hash": password_hash,
                "created_at": now,
                "updated_at": now,
            })
            
            user = {
                "id": user_id,
                "email": email,
                "username": username,
                "is_active": True,
                "created_at": now,
            }
            
            return True, "注册成功", user
        except Exception as e:
            logger.error(f"Failed to register user: {e}")
            return False, f"注册失败: {str(e)}", None
    
    def login_user(self, email: str, password: str) -> tuple[bool, str, Optional[dict]]:
        """Login a user.
        
        Returns:
            Tuple of (success, message, token_info)
        """
        email = email.lower()
        
        user = self.get_user_by_email(email)
        if not user:
            return False, "邮箱或密码错误", None
        
        if not self.verify_password(password, user["password_hash"]):
            return False, "邮箱或密码错误", None
        
        token, expires_in = self.create_access_token(user["id"], user["email"])
        
        return True, "登录成功", {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": expires_in,
        }
    
    def add_email_to_whitelist(self, email: str, added_by: str = "system") -> tuple[bool, str, Optional[dict]]:
        """Add an email to the whitelist.
        
        Returns:
            Tuple of (success, message, whitelist_entry)
        """
        email = email.lower()
        
        # Check if already exists
        if self.is_email_whitelisted(email):
            return False, "该邮箱已在白名单中", None
        
        entry_id = str(uuid.uuid4())
        now = datetime.now()
        
        insert_query = """
            INSERT INTO email_whitelist (id, email, added_by, is_active, created_at)
            VALUES (%(id)s, %(email)s, %(added_by)s, 1, %(created_at)s)
        """
        
        try:
            self.client.execute(insert_query, {
                "id": entry_id,
                "email": email,
                "added_by": added_by,
                "created_at": now,
            })
            
            entry = {
                "id": entry_id,
                "email": email,
                "added_by": added_by,
                "is_active": True,
                "created_at": now,
            }
            
            return True, "添加成功", entry
        except Exception as e:
            logger.error(f"Failed to add email to whitelist: {e}")
            return False, f"添加失败: {str(e)}", None
    
    def get_whitelist(self, limit: int = 100, offset: int = 0) -> list[dict]:
        """Get whitelist emails."""
        self._ensure_tables()
        query = """
            SELECT id, email, added_by, is_active, created_at
            FROM email_whitelist FINAL
            WHERE is_active = 1
            ORDER BY created_at DESC
            LIMIT %(limit)s OFFSET %(offset)s
        """
        result = self.client.execute(query, {"limit": limit, "offset": offset})
        
        return [
            {
                "id": row[0],
                "email": row[1],
                "added_by": row[2],
                "is_active": bool(row[3]),
                "created_at": row[4],
            }
            for row in result
        ]
    
    def import_whitelist_from_file(self, file_path: str) -> tuple[int, int]:
        """Import emails from a file to whitelist.
        
        Supports both semicolon-separated and newline-separated formats.
        
        Returns:
            Tuple of (imported_count, skipped_count)
        """
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"Whitelist file not found: {file_path}")
            return 0, 0
        
        content = path.read_text().strip()
        
        # Parse emails (support both ; and newline separators)
        if ";" in content:
            emails = [e.strip().lower() for e in content.split(";") if e.strip()]
        else:
            emails = [e.strip().lower() for e in content.split("\n") if e.strip()]
        
        imported = 0
        skipped = 0
        
        for email in emails:
            if not email or "@" not in email:
                continue
            
            success, _, _ = self.add_email_to_whitelist(email, added_by="file_import")
            if success:
                imported += 1
            else:
                skipped += 1
        
        logger.info(f"Whitelist import complete: {imported} imported, {skipped} skipped")
        return imported, skipped


# Singleton instance
_auth_service: Optional[AuthService] = None


def get_auth_service() -> AuthService:
    """Get the auth service singleton."""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service
