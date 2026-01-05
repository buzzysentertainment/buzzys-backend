from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from app.routers import email_test, booking, admin
from app.auth import verify_admin_token
from app.services.firebase_setup import db

# -------------------------
# CREATE APP
# -------------------------
app = FastAPI()

# -------------------------
# CORS CONFIG (PRODUCTION ONLY)
# -------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://www.buzzys.org",
        "https://buzzys.org"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------
# REGISTER ROUTERS
# -------------------------
app.include_router(email_test.router)
app.include_router(booking.router)
app.include_router(admin.router)

# -------------------------
# ROOT ENDPOINT
# -------------------------
@app.get("/")
def root():
    return {"message": "Backend is running!"}

# -------------------------
# ADMIN: GET ALL BOOKINGS
# (Only accessible with valid admin token)
# -------------------------
@app.get("/admin/bookings")
def get_all_bookings(user=Depends(verify_admin_token)):
    bookings_ref = db.collection("bookings")
    docs = bookings_ref.stream()

    bookings = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        bookings.append(data)

    return {"bookings": bookings}
