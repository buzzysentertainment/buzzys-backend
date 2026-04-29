from fastapi import APIRouter, HTTPException
import os
import requests

router = APIRouter(prefix="/utils", tags=["Utils"])

@router.post("/distance")
async def get_distance(data: dict):
    origin = data.get("origin")
    destination = data.get("destination")
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")

    if not origin or not destination:
        raise HTTPException(status_code=400, detail="Missing origin or destination")

    # Call Google Distance Matrix API
    url = (
        f"https://maps.googleapis.com/maps/api/distancematrix/json?"
        f"origins={origin}&destinations={destination}&units=imperial&key={AIzaSyAG9MA_9YDnT5rfzVDWF6kyNNU-aPR5DYc}"
    )
    
    try:
        response = requests.get(url)
        res_data = response.json()

        if res_data.get("status") == "OK":
            element = res_data["rows"][0]["elements"][0]
            if element.get("status") == "OK":
                # distance.value is in meters; convert to miles
                meters = element["distance"]["value"]
                miles = meters * 0.000621371
                return {"distance": miles}
            else:
                raise HTTPException(status_code=400, detail=f"Google Element Error: {element.get('status')}")
        
        raise HTTPException(status_code=400, detail="Google API Error: " + res_data.get("status", "Unknown"))
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))