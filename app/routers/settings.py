from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from app.auth import verify_admin_token

router = APIRouter(prefix="/admin/settings", tags=["Admin Settings"])

class ThemeSettings(BaseModel):
    primaryColor: str = Field(..., regex=r"^#([0-9a-fA-F]{6})$")
    secondaryColor: str = Field(..., regex=r"^#([0-9a-fA-F]{6})$")
    accentColor: str = Field(..., regex=r"^#([0-9a-fA-F]{6})$")
    backgroundColor: str = Field(..., regex=r"^#([0-9a-fA-F]{6})$")
    cardBackgroundColor: str = Field(..., regex=r"^#([0-9a-fA-F]{6})$")
    textColor: str = Field(..., regex=r"^#([0-9a-fA-F]{6})$")
    buttonRadius: int = Field(..., ge=0, le=40)

DEFAULT_THEME = {
    "primaryColor": "#ff7ac4",
    "secondaryColor": "#ffd166",
    "accentColor": "#7bdff2",
    "backgroundColor": "#ffffff",
    "cardBackgroundColor": "#f9f9ff",
    "textColor": "#222222",
    "buttonRadius": 12,
}

# TEMPORARY IN‑MEMORY STORAGE
THEME_STATE = DEFAULT_THEME.copy()

@router.get("/theme", response_model=ThemeSettings)
def get_theme_settings(admin=Depends(verify_admin_token)):
    return THEME_STATE

@router.put("/theme", response_model=ThemeSettings)
def update_theme_settings(
    new_settings: ThemeSettings,
    admin=Depends(verify_admin_token),
):
    global THEME_STATE
    THEME_STATE = new_settings.dict()
    return THEME_STATE
