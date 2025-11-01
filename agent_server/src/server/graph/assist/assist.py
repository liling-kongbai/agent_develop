from textwrap import dedent

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.output_parsers.pydantic import PydanticOutputParser  # 将非结构化输出解析为结构化的 Pydantic 对象
from langchain_core.prompts import ChatMessagePromptTemplate, ChatPromptTemplate
from langchain_core.runnables.base import RunnableSequence

from ..type import Intent, IntentClassification, Introspection, IntrospectionClassification


# 主图相关
async def create_intent_classifier_chain(llm: BaseChatModel) -> RunnableSequence:
    '''创建意图分类器链'''

    parser = PydanticOutputParser(pydantic_object=Intent)
    message_prompt_template = ChatMessagePromptTemplate.from_template(
        dedent(
            '''\
            下面使用 <<< 和 >>> 包裹的是对话列表，对话列表中的内容是用户和你的对话。
            <<<
                {messages}
            >>>
            请分析对话列表中的所有消息，“尤其”是用户的“最新的一条消息”，然后将用户接下来的意图分为以下之一：
                {intent_classification}
                如果只是普通的对话和聊天，请返回<<<{IntentClassification_ReactGraphAdapterNode}>>>。
            请注意，按照要求的格式返回相关的内容，不要输出错误的格式，不要输出错误的内容。
                {format_instruction}
            '''
        ),
        partial_variables={
            'intent_classification': '，'.join([i for i in IntentClassification]),
            'IntentClassification_ReactGraphAdapterNode': IntentClassification.ReactGraphAdapterNode,
            'format_instruction': parser.get_format_instructions(),
        },
        role='system',
    )  # 生成系统提示词，指导 LLM 按照指定的 Pydantic 对象输出 JSON 数据
    prompt_template = ChatPromptTemplate.from_messages([message_prompt_template])
    return prompt_template | llm | parser


async def create_introspection_classifier_chain(llm: BaseChatModel) -> RunnableSequence:
    '''创建反思分类器链'''

    parser = PydanticOutputParser(pydantic_object=Introspection)
    message_prompt_template = ChatMessagePromptTemplate.from_template(
        dedent(
            '''\
            你的任务是评估一个 AI 助手的回复草稿。

            下面是对话历史：
            <<<
                {messages}
            >>>

            AI 助手的回复草稿是：
            <<<
                {response_draft}
            >>>

            请评估这个回复草稿是否“充分且恰当”地回应了用户的最新消息。

            **评估指南:**
            1.  **简单问候或闲聊**: 如果用户只是在进行简单的问候（例如“你好”、“在吗？”）或闲聊，任何礼貌、相关的回复都应被视为“充分且恰当的”。
            2.  **明确问题或指令**: 如果用户提出了一个具体的问题或指令，请判断回复是否直接、准确地解决了该问题或指令。
            3.  **不完整或需要工具**: 如果回复明显不完整，或者用户的请求需要使用工具但回复中没有体现，那么它可能不是一个“充分且恰当的”回复。

            根据你的评估，返回以下选项之一：<<<{introspection_classification}>>>
            - 如果回复是“充分且恰当的”，请返回：<<<{IntrospectionClassification_AddFinalResponseNode}>>>
            - 如果回复“不充分或不恰当”，需要重新生成，请返回：<<<{IntrospectionClassification_IntentClassifierEntryNode}>>>
            
            请严格按照格式要求返回，不要包含任何其他解释。
                {format_instruction}
            '''
        ),
        partial_variables={
            'introspection_classification': ', '.join([e for e in IntrospectionClassification]),
            'IntrospectionClassification_AddFinalResponseNode': IntrospectionClassification.AddFinalResponseNode,
            'IntrospectionClassification_IntentClassifierEntryNode': IntrospectionClassification.IntentClassifierEntryNode,
            'format_instruction': parser.get_format_instructions(),
        },
        role='system',
    )
    prompt_template = ChatPromptTemplate.from_messages([message_prompt_template])
    return prompt_template | llm | parser


# 下面使用 <<< 和 >>> 包裹的是对话列表，对话列表中的内容是用户和你的对话。
# <<<
#     {messages}
# >>>
# 阅读最新的几条消息，分析用户的意图和要求，结合回复内容，请判断回复内容是否能满足用户的意图和要求，根据情况返回以下选项之一：<<<{introspection_classification}>>>
# 如果回复内容能满足用户的意图和要求，请返回<<<{IntrospectionClassification_AddFinalResponseNode}>>>;
# 如果回复内容能不能满足用户的意图和要求，请返回<<<{IntrospectionClassification_IntentClassifierEntryNode}>>>;
# 这是回复内容：
#     <<<{response_draft}>>>
# 请注意，按照要求的格式返回相关的内容，不要输出错误的格式，不要输出错误的内容。
#     {format_instruction}
