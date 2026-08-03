import hashlib
import os
import uuid
import jwt
from datetime import datetime, timedelta
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.models import User
# Import JWT_SECRET directly or define it locally to prevent circular imports
JWT_SECRET = os.getenv("JWT_SECRET", "super-secret-key")

def hash_password(password: str) -> str:
    """Hash password securely using standard PBKDF2-SHA256 (zero dependencies)."""
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return salt.hex() + "$" + key.hex()

def verify_password(stored_hash: str, password: str) -> bool:
    """Verify password by rehashing it and comparing with stored hash."""
    try:
        salt_hex, key_hex = stored_hash.split("$")
        salt = bytes.fromhex(salt_hex)
        key = bytes.fromhex(key_hex)
        new_key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
        return new_key == key
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False

def create_jwt_token(username: str) -> str:
    """Create a signed HS256 JWT token valid for 24 hours."""
    payload = {
        "sub": username,
        "exp": datetime.utcnow() + timedelta(hours=24),
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

async def seed_default_user_if_empty(db: AsyncSession) -> None:
    """Verify if the users table is empty. If empty, seed a default admin user."""
    try:
        result = await db.execute(select(User))
        existing_users = result.scalars().all()
        if not existing_users:
            default_username = os.getenv("ADMIN_USERNAME", "admin")
            default_password = os.getenv("ADMIN_PASSWORD", "admin123")
            
            hashed_pwd = hash_password(default_password)
            default_admin = User(
                username=default_username,
                hashed_password=hashed_pwd
            )
            db.add(default_admin)
            await db.commit()
            logger.info(f"SECURITY: Seeded default admin user '{default_username}' in Neon database.")
    except Exception as e:
        logger.error(f"Failed to seed default user: {e}")
        await db.rollback()
