from app.routers import tasks
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# EXISTING ROUTERS
from app.routers import email_test, booking, admin

# NEW SETTINGS ROUTERS
from app.routers.settings import (
    theme,
    homepage,
    pricing,
    booking_rules,
    business_info,
    media,
    admin_account
)

# FIREBASE
from app.services.firebase_setup import db


# -------------------------------------------------
# CREATE APP
# -------------------------------------------------
app = FastAPI()


# -------------------------------------------------
# CORS CONFIG (PRODUCTION ONLY)
# -------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://www.buzzys.org",
        "https://buzzys.org",
        "https://buzzysdatabase.web.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------------------------------
# REGISTER ROUTERS
# -------------------------------------------------

# Existing
app.include_router(email_test.router)
app.include_router(booking.router)
app.include_router(admin.router)
app.include_router(tasks.router)


# Settings (ALL admin settings panels)
app.include_router(theme.router, prefix="/admin", tags=["Theme"])
app.include_router(homepage.router, prefix="/admin", tags=["Homepage"])
app.include_router(pricing.router, prefix="/admin", tags=["Pricing"])
app.include_router(booking_rules.router, prefix="/admin", tags=["Booking Rules"])
app.include_router(business_info.router, prefix="/admin", tags=["Business Info"])
app.include_router(media.router, prefix="/admin", tags=["Media"])
app.include_router(admin_account.router, prefix="/admin", tags=["Admin Account"])


# -------------------------------------------------
# ROOT ENDPOINT
# -------------------------------------------------
@app.get("/")
def root():
    return {"message": "Backend is running!"}
