from fastapi import FastAPI, Depends
from app.routers import email_test, booking
from app.routers import admin
from app.auth import verify_admin_token
from app.services.firebase_setup import db

# -------------------------
# CREATE THE APP FIRST
# -------------------------
app = FastAPI()

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
# (You can delete this if admin router already has it)
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
