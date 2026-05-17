import json
from datetime import date, timedelta
from pathlib import Path

from trustvault.licensing.models import LicenceCheckResult, LicenceDocument


class LicenceValidator:
    """Initial licence validator.

    This validates licence structure and dates. Signature verification is deliberately isolated
    for the next implementation phase so the application can run in local development mode.
    """

    def __init__(self, licence_file: str):
        self.licence_file = Path(licence_file)

    def check(self, today: date | None = None) -> LicenceCheckResult:
        current_date = today or date.today()

        if not self.licence_file.exists():
            return LicenceCheckResult(state="missing", message="Licence file not found")

        try:
            payload = json.loads(self.licence_file.read_text(encoding="utf-8"))
            document = LicenceDocument.model_validate(payload)
        except Exception as exc:
            return LicenceCheckResult(state="invalid", message=f"Invalid licence file: {exc}")

        grace_until = document.valid_until + timedelta(days=document.grace_days)
        if current_date > grace_until:
            state = "expired"
            message = "Licence has expired and grace period has ended"
        elif current_date > document.valid_until:
            state = "grace"
            message = "Licence is expired but within grace period"
        elif current_date < document.valid_from:
            state = "not_yet_valid"
            message = "Licence is not yet valid"
        else:
            state = "valid"
            message = "Licence is valid"

        return LicenceCheckResult(
            state=state,
            licence_id=document.licence_id,
            customer_name=document.customer_name,
            edition=document.edition,
            valid_until=document.valid_until,
            modules=document.modules,
            message=message,
        )
