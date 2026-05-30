import hashlib, os, base64, hmac, secrets, logging
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt

logger = logging.getLogger("estacionamiento")

_jwt_secret = os.getenv("JWT_SECRET")
if not _jwt_secret:
    _jwt_secret = secrets.token_hex(32)
    logger.warning("JWT_SECRET no configurado. Usando secreto aleatorio. Configure JWT_SECRET en produccion.")
SECRET_KEY = _jwt_secret
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)
    return base64.b64encode(salt + key).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        raw = base64.b64decode(hashed)
        salt = raw[:16]
        stored_key = raw[16:]
        key = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt, 100000)
        return hmac.compare_digest(key, stored_key)
    except Exception:
        return False


def create_token(data: dict) -> str:
    to_encode = data.copy()
    to_encode.update({
        "exp": datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS),
        "iat": datetime.now(timezone.utc),
    })
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None