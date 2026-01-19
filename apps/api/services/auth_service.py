"""Authentication service for magic link authentication.

This service handles:
- User creation and lookup
- Magic link generation and validation
- JWT session token management
"""

import hashlib
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from pydantic import BaseModel, EmailStr

logger = logging.getLogger(__name__)

# Configuration
JWT_SECRET = os.getenv("JWT_SECRET", secrets.token_urlsafe(32))
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_DAYS = int(os.getenv("JWT_EXPIRY_DAYS", "7"))
MAGIC_LINK_EXPIRY_MINUTES = int(os.getenv("MAGIC_LINK_EXPIRY_MINUTES", "15"))


class User(BaseModel):
    """User model."""

    id: str
    email: str
    created_at: datetime
    last_login_at: Optional[datetime] = None
    is_active: bool = True
    resumes_generated: int = 0
    is_unlimited: bool = False


class MagicLink(BaseModel):
    """Magic link model."""

    id: str
    user_id: str
    token: str
    expires_at: datetime
    created_at: datetime


class SessionInfo(BaseModel):
    """Session information from JWT token."""

    user_id: str
    session_id: str
    expires_at: datetime


class AuthService:
    """Service for user authentication."""

    def __init__(self, database_url: Optional[str] = None):
        """Initialize the service.

        Args:
            database_url: Postgres connection string. If None, uses DATABASE_URL env var.
        """
        self.database_url = database_url or os.getenv("DATABASE_URL")
        self._connection = None

    def _get_connection(self):
        """Get or create database connection."""
        if not self.database_url:
            logger.warning("No DATABASE_URL configured, auth service disabled")
            return None

        if self._connection is None or self._connection.closed:
            try:
                import psycopg2

                self._connection = psycopg2.connect(self.database_url)
            except ImportError:
                logger.error("psycopg2 not installed, auth service disabled")
                return None
            except Exception as e:
                logger.error(f"Failed to connect to database: {e}")
                return None

        return self._connection

    def ensure_tables_exist(self) -> bool:
        """Create auth tables if they don't exist.

        Returns:
            True if tables exist or were created, False on error.
        """
        conn = self._get_connection()
        if not conn:
            return False

        try:
            cur = conn.cursor()

            # Create users table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    email VARCHAR(255) UNIQUE NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    last_login_at TIMESTAMP WITH TIME ZONE,
                    is_active BOOLEAN DEFAULT TRUE,
                    resumes_generated INTEGER DEFAULT 0,
                    is_unlimited BOOLEAN DEFAULT FALSE
                )
            """)

            # Add columns if they don't exist (for existing tables)
            cur.execute("""
                DO $$
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                                   WHERE table_name='users' AND column_name='resumes_generated') THEN
                        ALTER TABLE users ADD COLUMN resumes_generated INTEGER DEFAULT 0;
                    END IF;
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                                   WHERE table_name='users' AND column_name='is_unlimited') THEN
                        ALTER TABLE users ADD COLUMN is_unlimited BOOLEAN DEFAULT FALSE;
                    END IF;
                END $$;
            """)

            # Create magic_links table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS magic_links (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    token VARCHAR(255) UNIQUE NOT NULL,
                    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                    used_at TIMESTAMP WITH TIME ZONE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)

            # Create user_sessions table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_sessions (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    token_hash VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                    revoked_at TIMESTAMP WITH TIME ZONE,
                    user_agent TEXT,
                    ip_address VARCHAR(45)
                )
            """)

            # Create indexes
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_magic_links_token ON magic_links(token)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_magic_links_user_id ON magic_links(user_id)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_user_sessions_token_hash ON user_sessions(token_hash)"
            )

            conn.commit()
            cur.close()
            logger.info("Auth tables created/verified successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to create auth tables: {e}")
            conn.rollback()
            return False

    # ==================== User Management ====================

    def create_user(self, email: str) -> Optional[User]:
        """Create a new user.

        Args:
            email: User's email address (will be normalized to lowercase).

        Returns:
            User object if created successfully, None on error.
        """
        conn = self._get_connection()
        if not conn:
            return None

        email = email.lower().strip()

        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO users (email)
                VALUES (%s)
                RETURNING id, email, created_at, last_login_at, is_active
                """,
                (email,),
            )
            row = cur.fetchone()
            conn.commit()
            cur.close()

            if row:
                return User(
                    id=str(row[0]),
                    email=row[1],
                    created_at=row[2],
                    last_login_at=row[3],
                    is_active=row[4],
                )
            return None
        except Exception as e:
            logger.error(f"Failed to create user: {e}")
            conn.rollback()
            return None

    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email address.

        Args:
            email: User's email address.

        Returns:
            User object if found, None otherwise.
        """
        conn = self._get_connection()
        if not conn:
            return None

        email = email.lower().strip()

        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, email, created_at, last_login_at, is_active,
                       COALESCE(resumes_generated, 0), COALESCE(is_unlimited, FALSE)
                FROM users
                WHERE email = %s
                """,
                (email,),
            )
            row = cur.fetchone()
            cur.close()

            if row:
                return User(
                    id=str(row[0]),
                    email=row[1],
                    created_at=row[2],
                    last_login_at=row[3],
                    is_active=row[4],
                    resumes_generated=row[5],
                    is_unlimited=row[6],
                )
            return None
        except Exception as e:
            logger.error(f"Failed to get user by email: {e}")
            return None

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID.

        Args:
            user_id: User's UUID.

        Returns:
            User object if found, None otherwise.
        """
        conn = self._get_connection()
        if not conn:
            return None

        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, email, created_at, last_login_at, is_active,
                       COALESCE(resumes_generated, 0), COALESCE(is_unlimited, FALSE)
                FROM users
                WHERE id = %s
                """,
                (user_id,),
            )
            row = cur.fetchone()
            cur.close()

            if row:
                return User(
                    id=str(row[0]),
                    email=row[1],
                    created_at=row[2],
                    last_login_at=row[3],
                    is_active=row[4],
                    resumes_generated=row[5],
                    is_unlimited=row[6],
                )
            return None
        except Exception as e:
            logger.error(f"Failed to get user by id: {e}")
            return None

    def get_or_create_user(self, email: str) -> Optional[User]:
        """Get existing user or create new one.

        Args:
            email: User's email address.

        Returns:
            User object, or None on error.
        """
        user = self.get_user_by_email(email)
        if user:
            return user
        return self.create_user(email)

    def update_last_login(self, user_id: str) -> bool:
        """Update user's last login timestamp.

        Args:
            user_id: User's UUID.

        Returns:
            True if updated successfully.
        """
        conn = self._get_connection()
        if not conn:
            return False

        try:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE users
                SET last_login_at = NOW()
                WHERE id = %s
                """,
                (user_id,),
            )
            conn.commit()
            cur.close()
            return True
        except Exception as e:
            logger.error(f"Failed to update last login: {e}")
            conn.rollback()
            return False

    # ==================== Magic Link Management ====================

    def create_magic_link(self, user_id: str) -> Optional[MagicLink]:
        """Create a new magic link for user authentication.

        Args:
            user_id: User's UUID.

        Returns:
            MagicLink object if created successfully, None on error.
        """
        conn = self._get_connection()
        if not conn:
            return None

        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=MAGIC_LINK_EXPIRY_MINUTES
        )

        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO magic_links (user_id, token, expires_at)
                VALUES (%s, %s, %s)
                RETURNING id, user_id, token, expires_at, created_at
                """,
                (user_id, token, expires_at),
            )
            row = cur.fetchone()
            conn.commit()
            cur.close()

            if row:
                return MagicLink(
                    id=str(row[0]),
                    user_id=str(row[1]),
                    token=row[2],
                    expires_at=row[3],
                    created_at=row[4],
                )
            return None
        except Exception as e:
            logger.error(f"Failed to create magic link: {e}")
            conn.rollback()
            return None

    def validate_magic_link(self, token: str) -> Optional[User]:
        """Validate a magic link and return the associated user.

        The magic link is marked as used after successful validation.

        Args:
            token: The magic link token.

        Returns:
            User object if token is valid and not expired, None otherwise.
        """
        conn = self._get_connection()
        if not conn:
            return None

        try:
            cur = conn.cursor()

            # Find the magic link and associated user
            cur.execute(
                """
                SELECT ml.id, ml.user_id, ml.expires_at, ml.used_at,
                       u.id, u.email, u.created_at, u.last_login_at, u.is_active
                FROM magic_links ml
                JOIN users u ON ml.user_id = u.id
                WHERE ml.token = %s
                """,
                (token,),
            )
            row = cur.fetchone()

            if not row:
                cur.close()
                return None

            magic_link_id = row[0]
            expires_at = row[2]
            used_at = row[3]

            # Check if already used
            if used_at is not None:
                logger.warning(f"Magic link {magic_link_id} already used")
                cur.close()
                return None

            # Check if expired
            if expires_at < datetime.now(timezone.utc):
                logger.warning(f"Magic link {magic_link_id} expired")
                cur.close()
                return None

            # Mark as used
            cur.execute(
                """
                UPDATE magic_links
                SET used_at = NOW()
                WHERE id = %s
                """,
                (magic_link_id,),
            )
            conn.commit()
            cur.close()

            # Return the user
            return User(
                id=str(row[4]),
                email=row[5],
                created_at=row[6],
                last_login_at=row[7],
                is_active=row[8],
            )
        except Exception as e:
            logger.error(f"Failed to validate magic link: {e}")
            conn.rollback()
            return None

    def invalidate_magic_links_for_user(self, user_id: str) -> bool:
        """Invalidate all unused magic links for a user.

        Args:
            user_id: User's UUID.

        Returns:
            True if successful.
        """
        conn = self._get_connection()
        if not conn:
            return False

        try:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE magic_links
                SET used_at = NOW()
                WHERE user_id = %s AND used_at IS NULL
                """,
                (user_id,),
            )
            conn.commit()
            cur.close()
            return True
        except Exception as e:
            logger.error(f"Failed to invalidate magic links: {e}")
            conn.rollback()
            return False

    # ==================== Session/JWT Management ====================

    def create_session_token(
        self,
        user_id: str,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> Optional[str]:
        """Create a JWT session token for a user.

        Args:
            user_id: User's UUID.
            user_agent: Optional browser user agent string.
            ip_address: Optional client IP address.

        Returns:
            JWT token string if created successfully, None on error.
        """
        conn = self._get_connection()
        if not conn:
            return None

        session_id = secrets.token_urlsafe(16)
        expires_at = datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRY_DAYS)

        # Create JWT payload
        payload = {
            "sub": user_id,
            "sid": session_id,
            "exp": expires_at,
            "iat": datetime.now(timezone.utc),
        }

        try:
            # Generate JWT token
            token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

            # Hash the token for storage (we don't store raw tokens)
            token_hash = hashlib.sha256(token.encode()).hexdigest()

            # Store session in database
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO user_sessions (user_id, token_hash, expires_at, user_agent, ip_address)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (user_id, token_hash, expires_at, user_agent, ip_address),
            )
            conn.commit()
            cur.close()

            return token
        except Exception as e:
            logger.error(f"Failed to create session token: {e}")
            conn.rollback()
            return None

    def verify_session_token(self, token: str) -> Optional[SessionInfo]:
        """Verify a JWT session token.

        Args:
            token: The JWT token to verify.

        Returns:
            SessionInfo if valid, None otherwise.
        """
        try:
            # Decode and verify JWT
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])

            user_id = payload.get("sub")
            session_id = payload.get("sid")
            exp = payload.get("exp")

            if not user_id or not session_id:
                return None

            # Check if session is revoked in database
            conn = self._get_connection()
            if conn:
                token_hash = hashlib.sha256(token.encode()).hexdigest()

                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT revoked_at FROM user_sessions
                    WHERE token_hash = %s AND user_id = %s
                    """,
                    (token_hash, user_id),
                )
                row = cur.fetchone()
                cur.close()

                if row and row[0] is not None:
                    logger.warning(f"Session for user {user_id} has been revoked")
                    return None

            return SessionInfo(
                user_id=user_id,
                session_id=session_id,
                expires_at=datetime.fromtimestamp(exp, tz=timezone.utc),
            )
        except jwt.ExpiredSignatureError:
            logger.warning("Session token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid session token: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to verify session token: {e}")
            return None

    def revoke_session(self, token: str) -> bool:
        """Revoke a session token.

        Args:
            token: The JWT token to revoke.

        Returns:
            True if revoked successfully.
        """
        conn = self._get_connection()
        if not conn:
            return False

        try:
            token_hash = hashlib.sha256(token.encode()).hexdigest()

            cur = conn.cursor()
            cur.execute(
                """
                UPDATE user_sessions
                SET revoked_at = NOW()
                WHERE token_hash = %s AND revoked_at IS NULL
                """,
                (token_hash,),
            )
            conn.commit()
            cur.close()
            return True
        except Exception as e:
            logger.error(f"Failed to revoke session: {e}")
            conn.rollback()
            return False

    def revoke_all_sessions(self, user_id: str) -> bool:
        """Revoke all sessions for a user.

        Args:
            user_id: User's UUID.

        Returns:
            True if revoked successfully.
        """
        conn = self._get_connection()
        if not conn:
            return False

        try:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE user_sessions
                SET revoked_at = NOW()
                WHERE user_id = %s AND revoked_at IS NULL
                """,
                (user_id,),
            )
            conn.commit()
            cur.close()
            return True
        except Exception as e:
            logger.error(f"Failed to revoke all sessions: {e}")
            conn.rollback()
            return False

    def cleanup_expired_sessions(self) -> int:
        """Remove expired sessions from database.

        Returns:
            Number of sessions deleted.
        """
        conn = self._get_connection()
        if not conn:
            return 0

        try:
            cur = conn.cursor()
            cur.execute(
                """
                DELETE FROM user_sessions
                WHERE expires_at < NOW()
                """
            )
            deleted = cur.rowcount
            conn.commit()
            cur.close()
            return deleted
        except Exception as e:
            logger.error(f"Failed to cleanup expired sessions: {e}")
            conn.rollback()
            return 0

    def cleanup_used_magic_links(self, days_old: int = 1) -> int:
        """Remove old used magic links from database.

        Args:
            days_old: Remove links used more than this many days ago.

        Returns:
            Number of links deleted.
        """
        conn = self._get_connection()
        if not conn:
            return 0

        cutoff = datetime.now(timezone.utc) - timedelta(days=days_old)

        try:
            cur = conn.cursor()
            cur.execute(
                """
                DELETE FROM magic_links
                WHERE used_at IS NOT NULL AND used_at < %s
                """,
                (cutoff,),
            )
            deleted = cur.rowcount
            conn.commit()
            cur.close()
            return deleted
        except Exception as e:
            logger.error(f"Failed to cleanup used magic links: {e}")
            conn.rollback()
            return 0

    # ==================== Resume Limit Management ====================

    def can_create_resume(self, user_id: str, limit: int = 2) -> tuple[bool, int, int]:
        """Check if user can create another resume.

        Args:
            user_id: User's UUID.
            limit: Maximum resumes allowed (default 2).

        Returns:
            Tuple of (can_create, current_count, limit).
            can_create is True if user is unlimited or under limit.
        """
        user = self.get_user_by_id(user_id)
        if not user:
            return False, 0, limit

        if user.is_unlimited:
            return True, user.resumes_generated, -1  # -1 means unlimited

        return user.resumes_generated < limit, user.resumes_generated, limit

    def increment_resume_count(self, user_id: str) -> bool:
        """Increment the resume count for a user.

        Call this after successfully generating a resume.

        Args:
            user_id: User's UUID.

        Returns:
            True if incremented successfully.
        """
        conn = self._get_connection()
        if not conn:
            return False

        try:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE users
                SET resumes_generated = COALESCE(resumes_generated, 0) + 1
                WHERE id = %s
                """,
                (user_id,),
            )
            conn.commit()
            cur.close()
            return True
        except Exception as e:
            logger.error(f"Failed to increment resume count: {e}")
            conn.rollback()
            return False

    def set_unlimited(self, email: str, unlimited: bool = True) -> bool:
        """Set a user's unlimited status (admin function).

        Args:
            email: User's email address.
            unlimited: Whether to grant unlimited access.

        Returns:
            True if updated successfully.
        """
        conn = self._get_connection()
        if not conn:
            return False

        email = email.lower().strip()

        try:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE users
                SET is_unlimited = %s
                WHERE email = %s
                """,
                (unlimited, email),
            )
            updated = cur.rowcount > 0
            conn.commit()
            cur.close()
            return updated
        except Exception as e:
            logger.error(f"Failed to set unlimited status: {e}")
            conn.rollback()
            return False

    def close(self):
        """Close the database connection."""
        if self._connection and not self._connection.closed:
            self._connection.close()
            self._connection = None


# Singleton instance for use across the application
_auth_service: Optional[AuthService] = None


def get_auth_service() -> AuthService:
    """Get the singleton AuthService instance."""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
        _auth_service.ensure_tables_exist()
    return _auth_service
