"""Analysis failure codes; each becomes a stored failed test with that fail_reason."""

from typing import Literal

AnalysisErrorCode = Literal[
    "insufficient_valid_data", "no_descent_detected", "no_taps_detected", "sensor_disconnected"
]


class AnalysisError(Exception):
    def __init__(self, code: AnalysisErrorCode, message: str | None = None) -> None:
        super().__init__(message or code)
        self.code: AnalysisErrorCode = code
