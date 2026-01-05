import firebase_admin
from firebase_admin import auth as firebase_auth
from fastapi import HTTPException, Header

# This function verifies the Firebase ID token sent from the frontend
def verify_admin_token(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")

    try:
        token = authorization.split("Bearer ")[1]
        decoded_token = firebase_auth.verify_id_token(token)

        # Optional: restrict admin access to a specific email
        admin_email = "buzzysentertainment@gmail.com"  # change to your client’s email
        if decoded_token.get("email") != admin_email:
            raise HTTPException(status_code=403, detail="Not authorized")

        return decoded_token

    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
