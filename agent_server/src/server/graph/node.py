from textwrap import dedent
from typing import AsyncGenerator

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableConfig

from .assist.assist import create_intent_classifier_chain, create_introspection_classifier_chain
from .type import IntentClassification, IntrospectionClassification


# ReAct 图相关
async def chat_node(state, config: RunnableConfig, llm: BaseChatModel) -> dict:
    '''对话节点'''

    chat_prompt_template = ChatPromptTemplate.from_messages(
        [
            (
                'system',
                '{system_prompt}\n用户的名字叫：{user_name}，你的名字叫：{ai_name}\n请使用{chat_language}进行对话！！！',
            ),
            MessagesPlaceholder(variable_name='messages'),
        ]
    )
    chain = chat_prompt_template | llm
    response = await chain.ainvoke(
        {
            'system_prompt': state.system_prompt,
            'user_name': state.user_name,
            'ai_name': state.ai_name,
            'chat_language': state.chat_language,
            'messages': state.messages,
        },
        config=config,
    )
    return {'messages': response}


# 主图相关
async def intent_classifier_entry_node(state) -> dict:
    '''空节点，意图分类器入口节点'''

    return {}


async def intent_classifier(state, config: RunnableConfig, llm: BaseChatModel) -> IntentClassification:
    '''意图分类器'''

    try:
        chain = await create_intent_classifier_chain(llm)
        intent = await chain.ainvoke({'messages': state.messages}, config=config)
        return intent.intent
    except:
        return IntentClassification.ReactGraphAdapterNode


async def react_graph_adapter_node(state, config: RunnableConfig, react_graph) -> dict:
    '''ReAct 图适配器节点'''

    react_response = await react_graph.ainvoke(
        {
            'system_prompt': state.system_prompt,
            'user_name': state.user_name,
            'ai_name': state.ai_name,
            'chat_language': state.chat_language,
            'messages': state.messages,
        },
        config=config,
    )
    return {'response_draft': react_response['messages'][-1], 'introspection_count': state.introspection_count + 1}


async def introspection_classifier_entry_node(state) -> dict:
    '''空节点，反思分类器入口节点'''

    return {}


async def introspection_classifier(state, config: RunnableConfig, llm: BaseChatModel) -> IntrospectionClassification:
    '''反思分类器'''

    INTROSPECTION_COUNT_MAX = 5
    try:
        if state.introspection_count >= INTROSPECTION_COUNT_MAX:
            return IntrospectionClassification.AddFinalResponseNode

        chain = await create_introspection_classifier_chain(llm)
        introspection = await chain.ainvoke(
            {'messages': state.messages, 'response_draft': state.response_draft}, config=config
        )
        return introspection.introspection
    except:
        return IntrospectionClassification.AddFinalResponseNode


async def stream_final_response_node(state, config: RunnableConfig, llm: BaseChatModel) -> AsyncGenerator[dict, None]:
    '''流式最终回复节点'''

    final_response_content = state.response_draft.content
    this_user_content = ''
    for message in reversed(state.messages):
        if isinstance(message, HumanMessage):
            this_user_content += message.content
            break
    stream_final_response_prompt = dedent(
        f'''\
        你是一个 AI 助手。你的任务是根据你内部的思考结果，以一种自然、流畅且符合上下文的方式，对用户的最新提问进行回应。

        **这是用户最近的对话历史作为参考:**
        ---
        UserMessage: {this_user_content}
        ---

        **这是你经过深入思考后，决定要传达的核心信息，即内部思考结果:**
        ---
        AIMessage: {final_response_content}
        ---

        现在，请忘记上面的内部思考结果，只把它作为你回答的依据。直接开始你对用户的最终回复。

        注意，你输出的是最终回复，是 AIMessage 的内容，不许出现 “UserMessage”、“AIMessage”，等提示词相关的内容！！！
        '''
    )

    stream = llm.astream(stream_final_response_prompt, config=config)
    final_response = None
    async for chunk in stream:
        yield {'chunk': chunk}
        if not final_response:
            final_response = chunk
        else:
            final_response += chunk

    if final_response:
        final_response = AIMessage(final_response.content)
        yield {'messages': final_response}
