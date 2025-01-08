from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, create_model
from pydantic.fields import FieldInfo

from app.helpers.pydantic_types.phone_numbers import PhoneNumber


class TelecomFieldModel(BaseModel):
    """
    Field model for capturing telecom-related data.
    """
    name: str
    description: str
    type: str  # Possible types: "TEXT", "DATETIME", "EMAIL", "PHONE_NUMBER", "BOOLEAN"


class WorkflowInitiateModel(BaseModel):
    agent_phone_number: PhoneNumber
    bot_company: str = "More"
    bot_name: str
    service_fields: list[TelecomFieldModel] = [
        TelecomFieldModel(
            description="Customer's full name",
            name="customer_name",
            type="TEXT",
        ),
        TelecomFieldModel(
            description="Customer's email address",
            name="customer_email",
            type="EMAIL",
        ),
        TelecomFieldModel(
            description="Customer's phone number",
            name="customer_phone",
            type="PHONE_NUMBER",
        ),
        TelecomFieldModel(
            description="Address for the requested service",
            name="customer_address",
            type="TEXT",
        ),
        TelecomFieldModel(
            description="Type of service (e.g., nbn®, mobile)",
            name="service_type",
            type="TEXT",
        ),
        TelecomFieldModel(
            description="Is the address nbn® ready?",
            name="nbn_status",
            type="BOOLEAN",
        ),
        TelecomFieldModel(
            description="Preferred installation date",
            name="installation_date",
            type="DATETIME",
        ),
        TelecomFieldModel(
            description="Additional comments or requests",
            name="additional_comments",
            type="TEXT",
        ),
    ]
    lang: str = "en-US"
    prosody_rate: float = Field(
        default=1.0,
        ge=0.75,
        le=1.25,
    )
    task: str = (
        "Assist the customer with telecom inquiries, such as address verification, "
        "checking nbn® availability, setting up services, or answering questions about brodband and mobile plans. "
        "The conversation ends when the necessary information is gathered or the customer is satisfied."
    )

    def service_model(self) -> type[BaseModel]:
        return _fields_to_pydantic(
            name="ServiceEntryModel",
            fields=self.service_fields,
        )


class ConversationModel(BaseModel):
    initiate: WorkflowInitiateModel


def _fields_to_pydantic(name: str, fields: list[TelecomFieldModel]) -> type[BaseModel]:
    field_definitions = {field.name: _field_to_pydantic(field) for field in fields}
    return create_model(
        name,
        **field_definitions,  # pyright: ignore
        __config__=ConfigDict(
            extra="ignore",  # Avoid validation errors, just ignore data
        ),
    )


def _field_to_pydantic(
    field: TelecomFieldModel,
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
    data: str,
) -> type | Annotated[Any, ...]:
    match data:
        case "DATETIME":
            return datetime
        case "EMAIL":
            return EmailStr
        case "PHONE_NUMBER":
            return PhoneNumber
        case "BOOLEAN":
            return bool
        case "TEXT":
            return str
