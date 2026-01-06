import firebase_admin
from firebase_admin import auth as firebase_auth
from fastapi import HTTPException, Header
from passlib.context import CryptContext

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

# Verify Firebase ID token from frontend
def verify_admin_token(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")

    try:
        token = authorization.split("Bearer ")[1]
        decoded_token = firebase_auth.verify_id_token(token)

        # Optional: restrict admin access to a specific email
        admin_email = "buzzysentertainment@gmail.com"  # change if needed
        if decoded_token.get("email") != admin_email:
            raise HTTPException(status_code=403, detail="Not authorized")

        return decoded_token

    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
