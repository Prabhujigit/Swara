from enum import Enum

from pydantic import BaseModel, Field


class ActionEnum(str, Enum):
    CASE_CLOSED = "case_closed"
    PROVIDE_SERVICE_DETAILS = "provide_service_details"
    CUSTOMER_WILL_SEND_INFO = "customer_will_send_info"
    HIGH_PRIORITY = "high_priority"
    PROPOSE_NEW_PLAN = "propose_new_plan"
    REQUIRES_TECHNICAL_SUPPORT = "requires_technical_support"


class NextModel(BaseModel):
    action: ActionEnum = Field(
        description="Action to take after the call, based on the conversation, for the company."
    )
    justification: str = Field(
        description="""
        Justification for the selected action.

        # Rules
        - No more than a few sentences

        # Response examples
        - "Customer is satisfied with the explanation of the new nbn® plan. The case can be closed."
        - "Customer is unsure about the mobile plan options. A detailed brochure needs to be sent to their email."
        - "Customer reported slow internet speeds. The issue has been marked as high priority for technical support."
        - "Customer expressed interest in upgrading to a 5G-compatible mobile plan. A commercial offer should be proposed."
        - "Customer needs assistance setting up their modem. Technical support has been scheduled to call back."
        """
    )
