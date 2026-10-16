"""Runtime settings editable from the admin panel.

Each setting has an environment default (app/core/config.py); a row in `app_settings` overrides it.
Only operational settings live here -- secrets and infrastructure (database URL, JWT key, storage
credentials) are environment-only and never exposed to the admin API.
"""
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import AppSetting


@dataclass(frozen=True)
class SettingDef:
    key: str
    label: str
    group: str
    type: str  # bool | int | float
    description: str
    default: Callable[[], Any]
    min: Optional[float] = None
    max: Optional[float] = None


SETTING_DEFS: List[SettingDef] = [
    SettingDef("registration_enabled", "Allow self-registration", "Access", "bool",
               "When off, new faculty accounts can only be created by administrators.", lambda: True),
    SettingDef("uploads_enabled", "Accept new uploads", "Access", "bool",
               "Maintenance switch: when off, paper uploads are rejected with a maintenance message.", lambda: True),
    SettingDef("max_upload_size_mb", "Maximum upload size (MB)", "Uploads", "int",
               "Largest PDF/DOCX accepted by the upload endpoint.", lambda: settings.MAX_UPLOAD_SIZE_MB, 1, 100),
    SettingDef("exact_match_threshold", "Exact repetition threshold", "Similarity", "float",
               "Composite score at or above which a match is classed as an exact repeat.",
               lambda: settings.EXACT_MATCH_THRESHOLD, 0.05, 1.0),
    SettingDef("paraphrase_match_threshold", "Paraphrase threshold", "Similarity", "float",
               "Composite score at or above which a match is classed as paraphrased.",
               lambda: settings.PARAPHRASE_MATCH_THRESHOLD, 0.05, 1.0),
    SettingDef("conceptual_match_threshold", "Conceptual threshold", "Similarity", "float",
               "Lowest composite score reported as a (conceptual) match.",
               lambda: settings.CONCEPTUAL_MATCH_THRESHOLD, 0.05, 1.0),
    SettingDef("semantic_weight", "Semantic weight", "Similarity", "float",
               "Weight of embedding cosine similarity vs. BM25 in the composite score (0-1).",
               lambda: settings.SEMANTIC_WEIGHT, 0.0, 1.0),
    SettingDef("similarity_lookback_years", "Archive lookback (years)", "Similarity", "int",
               "How many academic years of the archive a draft is compared against.",
               lambda: settings.SIMILARITY_LOOKBACK_YEARS, 1, 50),
]
SETTING_BY_KEY: Dict[str, SettingDef] = {d.key: d for d in SETTING_DEFS}


@dataclass(frozen=True)
class RuntimeSettings:
    registration_enabled: bool
    uploads_enabled: bool
    max_upload_size_mb: int
    exact_match_threshold: float
    paraphrase_match_threshold: float
    conceptual_match_threshold: float
    semantic_weight: float
    similarity_lookback_years: int

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


class SettingValidationError(ValueError):
    pass


def coerce(defn: SettingDef, value: Any) -> Any:
    if defn.type == "bool":
        if not isinstance(value, bool):
            raise SettingValidationError(f"{defn.label} must be true or false.")
        return value
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SettingValidationError(f"{defn.label} must be a number.")
    if defn.type == "int":
        if float(value) != int(value):
            raise SettingValidationError(f"{defn.label} must be a whole number.")
        value = int(value)
    else:
        value = round(float(value), 4)
    if defn.min is not None and value < defn.min or defn.max is not None and value > defn.max:
        raise SettingValidationError(f"{defn.label} must be between {defn.min:g} and {defn.max:g}.")
    return value


def validate_combination(values: Dict[str, Any]) -> None:
    if not values["conceptual_match_threshold"] < values["paraphrase_match_threshold"] < values["exact_match_threshold"]:
        raise SettingValidationError("Thresholds must satisfy conceptual < paraphrase < exact.")


def stored_values(db: Session) -> Dict[str, AppSetting]:
    return {row.key: row for row in db.scalars(select(AppSetting).where(AppSetting.key.in_(list(SETTING_BY_KEY))))}


def current_values(db: Session) -> Dict[str, Any]:
    rows = stored_values(db)
    values = {}
    for defn in SETTING_DEFS:
        row = rows.get(defn.key)
        value = defn.default()
        if row is not None and row.value is not None:
            try:
                value = coerce(defn, row.value)
            except SettingValidationError:
                pass  # a corrupt override falls back to the default rather than breaking uploads
        values[defn.key] = value
    return values


def get_runtime_settings(db: Session) -> RuntimeSettings:
    return RuntimeSettings(**current_values(db))
