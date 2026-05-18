from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from trustvault.licensing.models import LicenceCheckResult
from trustvault.licensing.validator import LicenceValidator
from trustvault.settings import get_settings

router = APIRouter(prefix="/api/v1/licence", tags=["licence"])


@router.get("/status", response_model=LicenceCheckResult)
def licence_status() -> LicenceCheckResult:
    settings = get_settings()
    return LicenceValidator(settings.licence_file).check()


@router.post("/upload", response_model=LicenceCheckResult)
async def upload_licence(file: UploadFile = File(...)) -> LicenceCheckResult:
    settings = get_settings()
    filename = file.filename or "licence.json"
    if not filename.lower().endswith(".json"):
        raise HTTPException(status_code=400, detail="Licence file must be a JSON file")

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Licence file is empty")

    target = Path(settings.licence_file)
    target.parent.mkdir(parents=True, exist_ok=True)
    backup = target.with_suffix(target.suffix + ".bak")
    if target.exists():
        backup.write_bytes(target.read_bytes())

    target.write_bytes(contents)
    result = LicenceValidator(str(target)).check()
    if result.state in {"invalid", "expired", "not_yet_valid"}:
        if backup.exists():
            target.write_bytes(backup.read_bytes())
        else:
            target.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=result.message)

    return result
