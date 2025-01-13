from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, create_model
from pydantic.fields import FieldInfo

from app.helpers.pydantic_types.phone_numbers import PhoneNumber
from Swara.app.models.inquiry import InquiryFieldModel, InquiryTypeEnum


class LanguageEntryModel(BaseModel):
    """
    Language entry, containing the standard short code, an human name and the Azure Text-to-Speech voice name.

    See: https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support?tabs=tts#supported-languages
    """

    custom_voice_endpoint_id: str | None = None
    pronunciations_en: list[str]
    short_code: str
    voice: str

    @property
    def human_name(self) -> str:
        return self.pronunciations_en[0]

    def __str__(self):
        """
        Return the short code as string.
        """
        return self.short_code


class LanguageModel(BaseModel):
    """
    Manage language for the workflow.
    """

    default_short_code: str = "fr-FR"
    # Voice list from Azure TTS
    # See: https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support?tabs=tts
    availables: list[LanguageEntryModel] = [
        LanguageEntryModel(
            pronunciations_en=["English", "EN", "United States"],
            short_code="en-US",
            voice="en-US-ShimmerTurboMultilingualNeural",
        ),
    ]

    @property
    def default_lang(self) -> LanguageEntryModel:
        return next(
            (
                lang
                for lang in self.availables
                if self.default_short_code == lang.short_code
            ),
            self.availables[0],
        )


class WorkflowInitiateModel(BaseModel):
    agent_phone_number: PhoneNumber
    bot_company: str
    bot_name: str
    inquiry: list[InquiryFieldModel] = [
        InquiryFieldModel(
            description="Date and time of the Inquiry",
            name="inquiry_datetime",
            type=InquiryTypeEnum.DATETIME,
        ),
        InquiryFieldModel(
            description="Types of Service",
            name="service_name",
            type=InquiryTypeEnum.TEXT,
        ),
        InquiryFieldModel(
            description="Description of the Inquiry",
            name="inquiry_description",
            type=InquiryTypeEnum.TEXT,
        ),
        InquiryFieldModel(
            description="Additional requestor comment",
            name="comments",
            type=InquiryTypeEnum.TEXT,
        ),
    ]  # Configured like in v4 for compatibility
    lang: LanguageModel = LanguageModel()  # Object is fully defined by default
    prosody_rate: float = Field(
        default=1.0,
        ge=0.75,
        le=1.25,
    )
    task: str = "Assist the customer with Inquiry inquiries, such as address verification, checking nbn® availability, setting up services, or answering questions about brodband and mobile plans. The conversation ends when the necessary information is gathered or the customer is satisfied."

    def inquiry_model(self) -> type[BaseModel]:
        return _fields_to_pydantic(
            name="InquiryEntryModel",
            fields=[
                *self.inquiry,
                InquiryFieldModel(
                    description="Email of the customer",
                    name="customer_email",
                    type=InquiryTypeEnum.EMAIL,
                ),
                InquiryFieldModel(
                    description="First and last name of the customer",
                    name="customer_name",
                    type=InquiryTypeEnum.TEXT,
                ),
                InquiryFieldModel(
                    description="Phone number of the customer",
                    name="customer_phone",
                    type=InquiryTypeEnum.PHONE_NUMBER,
                ),
            ],
        )


class ConversationModel(BaseModel):
    # TODO: This could be simplified by removing the parent class but would cause a breaking change
    initiate: WorkflowInitiateModel


def _fields_to_pydantic(name: str, fields: list[InquiryFieldModel]) -> type[BaseModel]:
    field_definitions = {field.name: _field_to_pydantic(field) for field in fields}
    return create_model(
        name,
        **field_definitions,  # pyright: ignore
        __config__=ConfigDict(
            extra="ignore",  # Avoid validation errors, just ignore data
        ),
    )


def _field_to_pydantic(
    field: InquiryFieldModel,
) -> Annotated[Any, ...] | tuple[type, FieldInfo]:
    field_type = _type_to_pydantic(field.type)
    return (
        field_type | None,
        Field(
            default=None,
            description=field.description,
        ),
    )


def _type_to_pydantic(
    data: InquiryTypeEnum,
) -> type | Annotated[Any, ...]:
    match data:
        case InquiryTypeEnum.DATETIME:
            return datetime
        case InquiryTypeEnum.EMAIL:
            return EmailStr
        case InquiryTypeEnum.PHONE_NUMBER:
            return PhoneNumber
        case InquiryTypeEnum.TEXT:
            return str
