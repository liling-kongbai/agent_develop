from textwrap import dedent
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.prompts import ChatMessagePromptTemplate, ChatPromptTemplate
from langchain_core.runnables.base import RunnableSequence
from pydantic import BaseModel


class BaseStructuredOutputExtractor:
    '''结构化输出提取器'''

    OUTPUT_SCHEMA: BaseModel = NotImplemented
    SYSTEM_PROMPT: str = NotImplemented

    def __init__(self, llm: BaseChatModel):
        self._llm = llm
        try:
            self._llm_with_structured_output = self._llm.with_structured_output(self.OUTPUT_SCHEMA)
        except AttributeError:
            self._llm_with_structured_output = self._llm

    def _get_partial_variables(self) -> dict[str, Any]:
        '''获取部分变量的值，提供提示中部分变量的值'''

        return {}

    def get_extractor_chain(self) -> RunnableSequence:
        '''获取提取器链'''

        message_prompt_template = ChatMessagePromptTemplate.from_template(
            dedent(self.SYSTEM_PROMPT),
            partial_variables={
                **self._get_partial_variables(),
            },
            role='system',
        )
        chat_prompt_template = ChatPromptTemplate.from_messages([message_prompt_template])
        return chat_prompt_template | self._llm_with_structured_output
