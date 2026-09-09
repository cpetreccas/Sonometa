from dataclasses import dataclass, field
from typing import Dict, Tuple


@dataclass(frozen=True)
class ProcessingSnapshot:
    """Fotografia inmutable de una fila para procesar fuera del hilo UI."""

    row_id: str
    file_path: str
    values: Tuple[str, ...]


@dataclass(frozen=True)
class AdvancedFilterCriteria:
    """Contrato tipado para filtros avanzados de la grilla."""

    text: Dict[str, str] = field(default_factory=dict)
    combo: Dict[str, str] = field(default_factory=dict)
    toggles: Dict[str, bool] = field(default_factory=dict)

    def to_dict(self):
        return {
            "text": dict(self.text),
            "combo": dict(self.combo),
            "toggles": dict(self.toggles),
        }

    @staticmethod
    def from_dict(criteria):
        criteria = criteria or {}
        text = criteria.get("text", {}) if isinstance(criteria, dict) else {}
        combo = criteria.get("combo", {}) if isinstance(criteria, dict) else {}
        toggles = criteria.get("toggles", {}) if isinstance(criteria, dict) else {}

        safe_text = {str(k): str(v) for k, v in dict(text).items() if str(v).strip()}
        safe_combo = {str(k): str(v) for k, v in dict(combo).items() if str(v).strip()}
        safe_toggles = {str(k): bool(v) for k, v in dict(toggles).items()}

        return AdvancedFilterCriteria(text=safe_text, combo=safe_combo, toggles=safe_toggles)


