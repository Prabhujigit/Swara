from enum import Enum

from pydantic import BaseModel


class InquiryTypeEnum(str, Enum):
    DATETIME = "datetime"
    """Parsed to a Python datetime object."""
    EMAIL = "email"
    """Validated as an email address string."""
    PHONE_NUMBER = "phone_number"
    """Validated as a phone number string."""
    TEXT = "text"
    """Validated as a string."""


class InquiryFieldModel(BaseModel):
    description: str | None = None
    name: str
    type: InquiryTypeEnum
