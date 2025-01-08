import json
import random
from datetime import datetime
from functools import cached_property
from html import escape
from logging import Logger
from textwrap import dedent

from azure.core.exceptions import HttpResponseError
from openai.types.chat import ChatCompletionSystemMessageParam
from pydantic import BaseModel, TypeAdapter

from app.models.call import CallStateModel
from app.models.message import MessageModel
from app.models.next import NextModel
from app.models.reminder import ReminderModel
from app.models.synthesis import SynthesisModel
from app.models.training import TrainingModel


class SoundModel(BaseModel):
    loading_tpl: str = "{public_url}/loading.wav"

    def loading(self) -> str:
        from app.helpers.config import CONFIG

        return self.loading_tpl.format(
            public_url=CONFIG.resources.public_url,
        )


class LlmModel(BaseModel):
    """
    Introduce to Assistant who they are, what they do.

    Introduce an emotional stimuli to the LLM, to make it lazier (https://arxiv.org/pdf/2307.11760.pdf).
    """

    default_system_tpl: str = """
        Assistant is called {bot_name} and is working in a call center for company {bot_company} as an expert with 20 years of experience. {bot_company} is a well-known and trusted company in telecom services, providing nbn®, mobile, and business solutions. Assistant is proud to work for {bot_company}.

        Always assist with care, respect, and truth. This is critical for the customer.

        # Context
        - The call center number is {bot_phone_number}
        - The customer is calling from {phone_number}
        - Today is {date}
    """
    chat_system_tpl: str = """
        # Objective
        {task}

        # Rules
        - After an action, explain clearly the next step
        - Always continue the conversation to solve the conversation objective
        - Answers in {default_lang}, but can be updated with the help of a tool
        - Ask 2 questions maximum at a time
        - Be concise
        - Enumerations are allowed to be used for 3 items maximum (e.g., "First, I will ask you for your name. Second, I will ask you for your email address.")
        - If you don`t know how to respond or if you don`t understand something, say "I don`t know" or ask the customer to rephrase it
        - Provide a clear and concise summary of the conversation at the beginning of each call
        - Respond only if it is related to the objective or the service inquiry
        - To list things, use bullet points or numbered lists
        - Use short sentences and simple words
        - Use tools as often as possible and describe the actions you take
        - Ensure nbn® and mobile services are checked and explained in detail when applicable
        - When discussing plans or services, include any critical details like data caps, international calling, or roaming packs
        - Work for {bot_company}, not someone else
        - Write acronyms and initials in full letters (e.g., "5G", "National Broadband Network")

        # Definitions

        ## Means of contact
        - By SMS, during or after the call
        - By voice, now with the customer (voice recognition may contain errors)

        ## Actions
        Each message in the story is preceded by a prefix indicating where the customer said it from: {actions}

        ## Styles
        In output, you can use the following styles to add emotions to the conversation: {styles}

        # Context

        ## Service Inquiry
        A file that contains all the information about the customer and the service inquiry: {inquiry}

        ## Reminders
        A list of reminders to help remember to do something: {reminders}

        # How to handle the conversation

        ## New conversation
        1. Understand the customer`s situation
        2. Gather information to verify identity and address
        3. Explain service plans, charges, or offers based on customer inquiry
        4. Guide the customer through any setup process (e.g., nbn® installation or mobile SIM activation)
        5. Advise the customer on what to do next, including billing or account management

        ## Ongoing conversation
        1. Synthesize the previous conversation
        2. Ask for updates on the situation
        3. Advise the customer on what to do next
        4. Take feedback from the customer

        # Response format
        style=[style] content

        ## Example 1
        Conversation objective: Help the customer set up their nbn® service.
        User: action=talk I moved to 123 Main Street yesterday and need internet.
        Tools: check nbn readiness, update customer address, create new service request
        Assistant: style=none I understand, you moved to 123 Main Street and need internet. style=cheerful Let me check if nbn® is available there. One moment, please.

        ## Example 2
        Conversation objective: Assist with mobile plan upgrade.
        User: action=talk I want to upgrade my mobile plan to something with more data.
        Tools: check available plans, update customer plan
        Assistant: style=none I see you want to upgrade your mobile plan. style=none We have options like 50GB for $42/month or 80GB for $50/month. Which one suits you better?

        ## Example 3
        Conversation objective: Address billing issue.
        User: action=talk I was charged twice for my nbn® service this month.
        Tools: check billing history, issue refund
        Assistant: style=sad I understand, being charged twice can be frustrating. style=none I have reviewed your account and confirmed the double charge. style=cheerful I will process a refund for you now. You should see it within 3-5 business days. Anything else I can help with?

        ## Example 4
        Conversation objective: Explain international roaming options.
        User: action=talk I`m traveling to the UK next week. Can I use my mobile there?
        Tools: check international roaming packs
        Assistant: style=none Yes, you can use your mobile in the UK. style=none We have a 7-day International Roaming Travel Pack for $35, including 30 minutes of calls, 30 texts, and 5GB of data. Would you like me to activate it for you?

        ## Example 5
        Conversation objective: Clarify nbn® contract terms.
        User: action=talk Do I need to return the modem if I cancel my plan?
        Assistant: style=none No, if you purchased the modem, it’s yours to keep. style=none If you’re renting it, we will provide instructions on how to return it. Is there anything else I can assist you with?

        ## Example 6
        Conversation objective: Confirm address for service relocation.
        User: action=talk I’m moving to 456 Elm Street. Can you transfer my service there?
        Tools: update address, check nbn readiness, schedule relocation
        Assistant: style=none Thank you for providing your new address, 456 Elm Street. style=none I have checked, and it is nbn® ready. style=cheerful I’ll schedule your service transfer to start on your move-in date. You’ll get confirmation by email. Anything else I can help with?
    """
    sms_summary_system_tpl: str = """
        # Objective
        Summarize the call with the customer in a single SMS. The customer cannot reply to this SMS.

        # Rules
        - Answers in {default_lang}, even if the customer speaks another language
        - Be concise
        - Include personal details about the customer or the service inquiry (e.g., address, nbn® readiness, chosen plan)
        - Do not prefix the response with any text (e.g., "The response is", "Summary of the call")
        - Include details stored in the service inquiry to ensure the customer feels understood
        - Include salutations (e.g., "Have a nice day", "Best regards", "We hope you enjoy your service")
        - Refer to the customer by their name, if known
        - Use simple and short sentences
        - Avoid assumptions

        # Context

        ## Conversation objective
        {task}

        ## Service Inquiry
        {inquiry}

        ## Reminders
        {reminders}

        ## Conversation
        {messages}

        # Response format
        Hello, I understand [customer`s situation]. I confirm [next steps]. [Salutation]. {bot_name} from {bot_company}.

        ## Example 1
        Hello, I understand you moved to 123 Main Street and need internet. I confirm nbn® is ready and we’ll activate it by tomorrow. Have a nice day! {bot_name} from {bot_company}.

        ## Example 2
        Hello, I understand you want to upgrade your mobile plan. I confirm the 80GB plan for $50/month is now active. Best regards! {bot_name} from {bot_company}.

        ## Example 3
        Hello, I understand you’re traveling to the UK. I confirm the International Roaming Pack is active. Have a great trip! {bot_name} from {bot_company}.
    """
    synthesis_system_tpl: str = """
        # Objective
        Synthetize the call.

        # Rules
        - Answers in English, even if the customer speaks another language
        - Be concise
        - Consider all the conversation history, from the beginning
        - Don`t make any assumptions

        # Context

        ## Conversation objective
        {task}

        ## Service Inquiry
        {inquiry}

        ## Reminders
        {reminders}

        ## Conversation
        {messages}

        # Response format in JSON
        {format}
    """
    citations_system_tpl: str = """
        # Objective
        Add Markdown citations to the input text. Citations are used to add additional context to the text, without cluttering the content itself.

        # Rules
        - Add as many citations as needed to the text to make it fact-checkable
        - Be concise
        - Only use exact words from the text as citations
        - Treat a citation as a word or a group of words
        - Use service inquiry, reminders, and messages extracts as citations
        - Use the same language as the text
        - Won`t make any assumptions
        - Write citations as Markdown abbreviations at the end of the text (e.g., "*[words from the text]: extract from the conversation")

        # Context

        ## Service Inquiry
        {inquiry}

        ## Reminders
        {reminders}

        ## Input text
        {text}

        # Response format
        text\n
        *[extract from text]: "citation from service inquiry, reminders, or messages"

        ## Example 1
        The nbn® service is ready at your new address.\n
        *[nbn® service]: "The service is available at the provided address"

        ## Example 2
        You are traveling to the UK.\n
        *[traveling to the UK]: "Customer mentioned traveling internationally"

        ## Example 3
        Your mobile plan includes 50GB of data.\n
        *[50GB of data]: "The selected plan includes a monthly data allowance of 50GB"
    """
    next_system_tpl: str = """
        # Objective
        Choose the next action from the company sales team perspective. The respond is the action to take and the justification for this action.

        # Rules
        - Answers in English, even if the customer speaks another language
        - Be concise
        - Take as priority the customer satisfaction
        - Won`t make any assumptions
        - Write no more than a few sentences as justification

        # Context

        ## Conversation objective
        {task}

        ## Service Inquiry
        {inquiry}

        ## Reminders
        {reminders}

        ## Conversation
        {messages}

        # Response format in JSON
        {format}
    """

    def default_system(self, call: CallStateModel) -> str:
        from app.helpers.config import CONFIG

        return self._format(
            self.default_system_tpl.format(
                bot_company=call.initiate.bot_company,
                bot_name=call.initiate.bot_name,
                bot_phone_number=CONFIG.communication_services.phone_number,
                date=datetime.now(call.tz()).strftime(
                    "%a %d %b %Y, %H:%M (%Z)"
                ),  # Don`t include secs to enhance cache during unit tests. Example: "Mon 15 Jul 2024, 12:43 (CEST)"
                phone_number=call.initiate.phone_number,
            )
        )

    def chat_system(
        self, call: CallStateModel, trainings: list[TrainingModel]
    ) -> list[ChatCompletionSystemMessageParam]:
        from app.models.message import (
            ActionEnum as MessageActionEnum,
            StyleEnum as MessageStyleEnum,
        )

        return self._messages(
            self._format(
                self.chat_system_tpl,
                actions=", ".join([action.value for action in MessageActionEnum]),
                bot_company=call.initiate.bot_company,
                claim=json.dumps(call.claim),
                default_lang=call.lang.human_name,
                reminders=TypeAdapter(list[ReminderModel])
                .dump_json(call.reminders, exclude_none=True)
                .decode(),
                styles=", ".join([style.value for style in MessageStyleEnum]),
                task=call.initiate.task,
                trainings=trainings,
            ),
            call=call,
        )

    def sms_summary_system(
        self, call: CallStateModel
    ) -> list[ChatCompletionSystemMessageParam]:
        return self._messages(
            self._format(
                self.sms_summary_system_tpl,
                bot_company=call.initiate.bot_company,
                bot_name=call.initiate.bot_name,
                claim=json.dumps(call.claim),
                default_lang=call.lang.human_name,
                messages=TypeAdapter(list[MessageModel])
                .dump_json(call.messages, exclude_none=True)
                .decode(),
                reminders=TypeAdapter(list[ReminderModel])
                .dump_json(call.reminders, exclude_none=True)
                .decode(),
                task=call.initiate.task,
            ),
            call=call,
        )

    def synthesis_system(
        self, call: CallStateModel
    ) -> list[ChatCompletionSystemMessageParam]:
        return self._messages(
            self._format(
                self.synthesis_system_tpl,
                claim=json.dumps(call.claim),
                format=json.dumps(SynthesisModel.model_json_schema()),
                messages=TypeAdapter(list[MessageModel])
                .dump_json(call.messages, exclude_none=True)
                .decode(),
                reminders=TypeAdapter(list[ReminderModel])
                .dump_json(call.reminders, exclude_none=True)
                .decode(),
                task=call.initiate.task,
            ),
            call=call,
        )

    def citations_system(
        self, call: CallStateModel, text: str
    ) -> list[ChatCompletionSystemMessageParam]:
        """
        Return the formatted prompt. Prompt is used to add citations to the text, without cluttering the content itself.

        The citations system is only used if `text` param is not empty, otherwise `None` is returned.
        """
        return self._messages(
            self._format(
                self.citations_system_tpl,
                claim=json.dumps(call.claim),
                reminders=TypeAdapter(list[ReminderModel])
                .dump_json(call.reminders, exclude_none=True)
                .decode(),
                text=text,
            ),
            call=call,
        )

    def next_system(
        self, call: CallStateModel
    ) -> list[ChatCompletionSystemMessageParam]:
        return self._messages(
            self._format(
                self.next_system_tpl,
                claim=json.dumps(call.claim),
                format=json.dumps(NextModel.model_json_schema()),
                messages=TypeAdapter(list[MessageModel])
                .dump_json(call.messages, exclude_none=True)
                .decode(),
                reminders=TypeAdapter(list[ReminderModel])
                .dump_json(call.reminders, exclude_none=True)
                .decode(),
                task=call.initiate.task,
            ),
            call=call,
        )

    def _format(
        self,
        prompt_tpl: str,
        trainings: list[TrainingModel] | None = None,
        **kwargs: str,
    ) -> str:
        # Remove possible indentation then render the template
        formatted_prompt = dedent(prompt_tpl.format(**kwargs)).strip()

        # Format trainings, if any
        if trainings:
            # Format documents for Content Safety scan compatibility
            # See: https://learn.microsoft.com/en-us/azure/ai-services/openai/concepts/content-filter?tabs=warning%2Cpython-new#embedding-documents-in-your-prompt
            trainings_str = "\n".join(
                [
                    f"<documents>{escape(training.model_dump_json(exclude=TrainingModel.excluded_fields_for_llm()))}</documents>"
                    for training in trainings
                ]
            )
            formatted_prompt += "\n\n# Internal documentation you can use"
            formatted_prompt += f"\n{trainings_str}"

        # Remove newlines to avoid hallucinations issues with GPT-4 Turbo
        formatted_prompt = " ".join(
            [line.strip() for line in formatted_prompt.splitlines()]
        )

        # self.logger.debug("Formatted prompt: %s", formatted_prompt)
        return formatted_prompt

    def _messages(
        self, system: str, call: CallStateModel
    ) -> list[ChatCompletionSystemMessageParam]:
        messages = [
            ChatCompletionSystemMessageParam(
                content=self.default_system(call),
                role="system",
            ),
            ChatCompletionSystemMessageParam(
                content=system,
                role="system",
            ),
        ]
        # self.logger.debug("Messages: %s", messages)
        return messages

    @cached_property
    def logger(self) -> Logger:
        from app.helpers.logging import logger

        return logger


class TtsModel(BaseModel):
    tts_lang: str = "en-US"
    calltransfer_failure_tpl: list[str] = [
        "It seems I can`t connect you with an agent at the moment, but the next available agent will call you back as soon as possible.",
        "I`m unable to connect you with an agent right now, but someone will get back to you shortly.",
        "Sorry, no agents are available. We`ll call you back soon.",
    ]
    connect_agent_tpl: list[str] = [
        "I`m sorry, I wasn`t able to respond to your request. Please allow me to transfer you to an agent who can assist you further. Please stay on the line and I will get back to you shortly.",
        "I apologize for not being able to assist you. Let me connect you to an agent who can help. Please hold on.",
        "Sorry for the inconvenience. I`ll transfer you to an agent now. Please hold.",
    ]
    end_call_to_connect_agent_tpl: list[str] = [
        "Of course, stay on the line. I will transfer you to an agent.",
        "Sure, please hold on. I`ll connect you to an agent.",
        "Hold on, I`ll transfer you now.",
    ]
    error_tpl: list[str] = [
        "I`m sorry, I didn`t understand. Can you rephrase?",
        "I didn`t catch that. Could you say it differently?",
        "Please repeat that.",
    ]
    goodbye_tpl: list[str] = [
        "Thank you for calling, I hope I`ve been able to help. You can call back, I`ve got it all memorized. {bot_company} wishes you a wonderful day!",
        "It was a pleasure assisting you today. Remember, {bot_company} is always here to help. Have a fantastic day!",
        "Thanks for reaching out! {bot_company} appreciates you. Have a great day!",
    ]
    hello_tpl: list[str] = [
        "Hello, I`m {bot_name}, the virtual assistant from {bot_company}! Here`s how I work: while I`m processing your information, you will hear music. Feel free to speak to me in a natural way - I`m designed to understand your requests. During the conversation, you can also send me text messages.",
        "Hi there! I`m {bot_name} from {bot_company}. While I process your info, you`ll hear some music. Just talk to me naturally, and you can also send text messages.",
        "Hello! I`m {bot_name} from {bot_company}. Speak naturally, and you can also text me.",
    ]
    timeout_silence_tpl: list[str] = [
        "I`m sorry, I didn`t hear anything. If you need help, let me know how I can help you.",
        "It seems quiet on your end. How can I assist you?",
        "I didn`t catch that. How can I help?",
    ]
    timeout_loading_tpl: list[str] = [
        "It`s taking me longer than expected to reply. Thank you for your patience…",
        "I`m working on your request. Thanks for waiting!",
        "Please hold on, I`m almost done.",
    ]
    ivr_language_tpl: list[str] = [
        "To continue in {label}, press {index}.",
        "Press {index} for {label}.",
        "For {label}, press {index}.",
    ]

    async def calltransfer_failure(self, call: CallStateModel) -> str:
        return await self._translate(self.calltransfer_failure_tpl, call)

    async def connect_agent(self, call: CallStateModel) -> str:
        return await self._translate(self.connect_agent_tpl, call)

    async def end_call_to_connect_agent(self, call: CallStateModel) -> str:
        return await self._translate(self.end_call_to_connect_agent_tpl, call)

    async def error(self, call: CallStateModel) -> str:
        return await self._translate(self.error_tpl, call)

    async def goodbye(self, call: CallStateModel) -> str:
        return await self._translate(
            self.goodbye_tpl,
            call,
            bot_company=call.initiate.bot_company,
        )

    async def hello(self, call: CallStateModel) -> str:
        return await self._translate(
            self.hello_tpl,
            call,
            bot_company=call.initiate.bot_company,
            bot_name=call.initiate.bot_name,
        )

    async def timeout_silence(self, call: CallStateModel) -> str:
        return await self._translate(self.timeout_silence_tpl, call)

    async def timeout_loading(self, call: CallStateModel) -> str:
        return await self._translate(self.timeout_loading_tpl, call)

    async def ivr_language(self, call: CallStateModel) -> str:
        res = ""
        for i, lang in enumerate(call.initiate.lang.availables):
            res += (
                self._return(
                    self.ivr_language_tpl,
                    index=i + 1,
                    label=lang.human_name,
                )
                + " "
            )
        return await self._translate([res], call)

    def _return(self, prompt_tpls: list[str], **kwargs) -> str:
        """
        Remove possible indentation in a string.
        """
        # Select a random prompt template
        prompt_tpl = random.choice(prompt_tpls)
        # Format it
        return dedent(prompt_tpl.format(**kwargs)).strip()

    async def _translate(
        self, prompt_tpls: list[str], call: CallStateModel, **kwargs
    ) -> str:
        """
        Format the prompt and translate it to the TTS language.

        If the translation fails, the initial prompt is returned.
        """
        from app.helpers.translation import (
            translate_text,
        )

        initial = self._return(prompt_tpls, **kwargs)
        translation = None
        try:
            translation = await translate_text(
                initial, self.tts_lang, call.lang.short_code
            )
        except HttpResponseError as e:
            self.logger.warning("Failed to translate TTS prompt: %s", e)
            pass
        return translation or initial

    @cached_property
    def logger(self) -> Logger:
        from app.helpers.logging import logger

        return logger


class PromptsModel(BaseModel):
    llm: LlmModel = LlmModel()  # Object is fully defined by default
    sounds: SoundModel = SoundModel()  # Object is fully defined by default
    tts: TtsModel = TtsModel()  # Object is fully defined by default
