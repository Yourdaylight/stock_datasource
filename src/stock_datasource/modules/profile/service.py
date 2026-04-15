"""Profile service for managing portfolio profiles (multi-account).

A profile represents a single brokerage account. Each user can have
multiple profiles (e.g., "中信证券", "华泰证券"). Positions are scoped
to a profile. Every user automatically gets a default profile.
"""

import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class ProfileService:
    """CRUD service for portfolio profiles."""

    def __init__(self):
        self._db = None

    @property
    def db(self):
        """Lazy load database client."""
        if self._db is None:
            try:
                from stock_datasource.models.database import db_client
                self._db = db_client
            except Exception as e:
                logger.warning("Failed to get DB client: %s", e)
        return self._db

    # ------------------------------------------------------------------
    # Ensure table exists
    # ------------------------------------------------------------------

    def ensure_table(self):
        """Create portfolio_profiles table if not exists."""
        if self.db is None:
            return
        try:
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS portfolio_profiles (
                    id String,
                    user_id String,
                    name String,
                    broker String DEFAULT '',
                    is_default UInt8 DEFAULT 0,
                    is_active UInt8 DEFAULT 1,
                    created_at DateTime DEFAULT now(),
                    updated_at DateTime DEFAULT now()
                ) ENGINE = ReplacingMergeTree(updated_at)
                ORDER BY (user_id, id)
                SETTINGS index_granularity = 8192
            """)
        except Exception as e:
            logger.warning("Failed to ensure portfolio_profiles table: %s", e)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_profile(
        self,
        user_id: str,
        name: str,
        broker: str = "",
        is_default: bool = False,
    ) -> Dict:
        """Create a new profile for a user."""
        self.ensure_table()

        profile_id = str(uuid.uuid4())
        now = datetime.now()

        profile = {
            "id": profile_id,
            "user_id": user_id,
            "name": name,
            "broker": broker,
            "is_default": is_default,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }

        if self.db is not None:
            try:
                self.db.execute(
                    """INSERT INTO portfolio_profiles
                       (id, user_id, name, broker, is_default, is_active, created_at, updated_at)
                       VALUES (%(id)s, %(user_id)s, %(name)s, %(broker)s,
                               %(is_default)s, 1, %(created_at)s, %(updated_at)s)""",
                    {
                        "id": profile_id,
                        "user_id": user_id,
                        "name": name,
                        "broker": broker,
                        "is_default": 1 if is_default else 0,
                        "created_at": now,
                        "updated_at": now,
                    },
                )
                logger.info("Profile %s created for user %s: %s", profile_id, user_id, name)
            except Exception as e:
                logger.warning("Failed to save profile to database: %s", e)

        return profile

    def list_profiles(self, user_id: str) -> List[Dict]:
        """List all active profiles for a user."""
        self.ensure_table()

        if self.db is None:
            return []

        try:
            df = self.db.execute_query(
                """SELECT id, user_id, name, broker, is_default, created_at, updated_at
                   FROM portfolio_profiles FINAL
                   WHERE user_id = %(user_id)s AND is_active = 1
                   ORDER BY is_default DESC, created_at ASC""",
                {"user_id": user_id},
            )
            if df.empty:
                return []
            return self._df_to_profiles(df)
        except Exception as e:
            logger.warning("Failed to list profiles: %s", e)
            return []

    def get_profile(self, profile_id: str, user_id: str) -> Optional[Dict]:
        """Get a single profile by id (owned by user)."""
        self.ensure_table()

        if self.db is None:
            return None

        try:
            df = self.db.execute_query(
                """SELECT id, user_id, name, broker, is_default, created_at, updated_at
                   FROM portfolio_profiles FINAL
                   WHERE id = %(id)s AND user_id = %(user_id)s AND is_active = 1
                   LIMIT 1""",
                {"id": profile_id, "user_id": user_id},
            )
            if df.empty:
                return None
            profiles = self._df_to_profiles(df)
            return profiles[0] if profiles else None
        except Exception as e:
            logger.warning("Failed to get profile: %s", e)
            return None

    def update_profile(
        self,
        profile_id: str,
        user_id: str,
        name: Optional[str] = None,
        broker: Optional[str] = None,
    ) -> Optional[Dict]:
        """Update a profile's name and/or broker."""
        profile = self.get_profile(profile_id, user_id)
        if profile is None:
            return None

        if name is not None:
            profile["name"] = name
        if broker is not None:
            profile["broker"] = broker
        profile["updated_at"] = datetime.now().isoformat()

        if self.db is not None:
            try:
                now = datetime.now()
                self.db.execute(
                    """INSERT INTO portfolio_profiles
                       (id, user_id, name, broker, is_default, is_active, created_at, updated_at)
                       VALUES (%(id)s, %(user_id)s, %(name)s, %(broker)s,
                               %(is_default)s, 1, %(created_at)s, %(updated_at)s)""",
                    {
                        "id": profile_id,
                        "user_id": user_id,
                        "name": profile["name"],
                        "broker": profile["broker"],
                        "is_default": 1 if profile["is_default"] else 0,
                        "created_at": profile["created_at"],
                        "updated_at": now,
                    },
                )
            except Exception as e:
                logger.warning("Failed to update profile: %s", e)

        return profile

    def delete_profile(self, profile_id: str, user_id: str) -> bool:
        """Soft-delete a profile. Cannot delete the default profile."""
        profile = self.get_profile(profile_id, user_id)
        if profile is None:
            return False

        if profile.get("is_default"):
            logger.warning("Cannot delete default profile %s", profile_id)
            return False

        if self.db is not None:
            try:
                # ReplacingMergeTree: re-insert with is_active=0
                now = datetime.now()
                self.db.execute(
                    """INSERT INTO portfolio_profiles
                       (id, user_id, name, broker, is_default, is_active, created_at, updated_at)
                       VALUES (%(id)s, %(user_id)s, %(name)s, %(broker)s,
                               %(is_default)s, 0, %(created_at)s, %(updated_at)s)""",
                    {
                        "id": profile_id,
                        "user_id": user_id,
                        "name": profile["name"],
                        "broker": profile["broker"],
                        "is_default": 1 if profile["is_default"] else 0,
                        "created_at": profile.get("created_at", now.isoformat()),
                        "updated_at": now,
                    },
                )
                logger.info("Profile %s deleted for user %s", profile_id, user_id)
            except Exception as e:
                logger.warning("Failed to delete profile: %s", e)
                return False

        return True

    def ensure_default_profile(self, user_id: str) -> Dict:
        """Ensure user has a default profile. Create one if missing."""
        profiles = self.list_profiles(user_id)
        defaults = [p for p in profiles if p.get("is_default")]
        if defaults:
            return defaults[0]

        return self.create_profile(
            user_id=user_id,
            name="默认账户",
            broker="",
            is_default=True,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _df_to_profiles(df: pd.DataFrame) -> List[Dict]:
        """Convert DataFrame to list of profile dicts."""
        profiles = []
        for _, row in df.iterrows():
            profiles.append({
                "id": str(row["id"]),
                "user_id": str(row["user_id"]),
                "name": str(row["name"]),
                "broker": str(row["broker"]) if pd.notna(row["broker"]) else "",
                "is_default": bool(row["is_default"]) if pd.notna(row.get("is_default")) else False,
                "created_at": str(row["created_at"]) if pd.notna(row.get("created_at")) else "",
                "updated_at": str(row["updated_at"]) if pd.notna(row.get("updated_at")) else "",
            })
        return profiles


# Singleton
_profile_service: Optional[ProfileService] = None


def get_profile_service() -> ProfileService:
    global _profile_service
    if _profile_service is None:
        _profile_service = ProfileService()
    return _profile_service
