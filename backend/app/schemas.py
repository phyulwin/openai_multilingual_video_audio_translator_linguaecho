# schemas.py — Strict request and model-output contracts.
from pydantic import BaseModel, ConfigDict, Field, field_validator
from .config import SUPPORTED, VOICES


class StrictModel(BaseModel):
    """Reject accidental and malicious extra fields."""
    model_config = ConfigDict(extra='forbid')


class ProcessRequest(StrictModel):
    """Validate capability choices before spending API credits."""
    source: str = 'auto'
    target: str = 'en'
    voice: str = 'coral'

    @field_validator('source', 'target')
    @classmethod
    def language(cls, value, info):
        """Limit the full speech pipeline to documented speech languages."""
        if value not in SUPPORTED and not (info.field_name == 'source' and value == 'auto'):
            raise ValueError('This language is not supported by the configured speech pipeline.')
        return value

    @field_validator('voice')
    @classmethod
    def voice_supported(cls, value):
        """Only accept built-in voices; voice cloning is not supported."""
        if value not in VOICES:
            raise ValueError('Unsupported voice')
        return value


class ProjectPatch(StrictModel):
    """Allow metadata edits without access to internal filenames."""
    name: str | None = Field(default=None, min_length=1, max_length=200)
    favorite: bool | None = None


class SegmentPatch(StrictModel):
    """Translation edits cannot change original text or timestamps."""
    target: str = 'en'
    translated_text: str | None = Field(default=None, min_length=1, max_length=4000)
    favorite: bool | None = None


class TranslationItem(StrictModel):
    """Retain one translated string for each immutable source identifier."""
    id: int
    translated_text: str


class TranslationResult(StrictModel):
    """Structured output schema consumed by the OpenAI SDK."""
    source_language: str
    target_language: str
    segments: list[TranslationItem]
