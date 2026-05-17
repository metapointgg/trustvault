from fastapi import APIRouter

from trustvault.licensing.models import LicenceCheckResult
from trustvault.licensing.validator import LicenceValidator
from trustvault.settings import get_settings

router = APIRouter(prefix="/api/v1/licence", tags=["licence"])


@router.get("/status", response_model=LicenceCheckResult)
def licence_status() -> LicenceCheckResult:
    settings = get_settings()
    return LicenceValidator(settings.licence_file).check()
