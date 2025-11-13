from functools import partial  # 固定函数的部分参数，返回偏函数

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from .assist.type import IntentClassification, IntrospectionClassification
from .node import (
    chat_node,
    intent_classifier_condition,
    intent_classifier_entry_node,
    introspection_classifier_condition,
    introspection_classifier_entry_node,
    react_graph_adapter_node,
    remind_task_extraction_node,
    stream_final_response_node,
)
from .state import MainState, ReActState


async def create_react_graph(chat_node: chat_node, llm: BaseChatModel, tools: list | None = None):
    '''创建 ReAct 图'''

    react_graph_builder = StateGraph(ReActState)
    react_graph_builder.add_node('chat_node', partial(chat_node, llm=llm))

    react_graph_builder.add_edge(START, 'chat_node')

    if tools:
        react_graph_builder.add_node('tool_node', ToolNode(tools))

        react_graph_builder.add_conditional_edges('chat_node', tools_condition, {'tools': 'tool_node', '__end__': END})
        react_graph_builder.add_edge('tool_node', 'chat_node')
    else:
        react_graph_builder.add_edge('chat_node', END)
    return react_graph_builder.compile()


async def create_main_graph_builder(
    chat_node: chat_node, llm: BaseChatModel, remind_task_manager, tools: list | None = None
):
    '''创建主图构建器，意图分类路由，反思评分分类路由'''

    main_graph_builder = StateGraph(MainState)
    main_graph_builder.add_node('intent_classifier_entry_node', intent_classifier_entry_node)
    main_graph_builder.add_node(
        'react_graph_adapter_node',
        partial(react_graph_adapter_node, react_graph=await create_react_graph(chat_node, llm, tools)),
    )
    main_graph_builder.add_node(
        'remind_task_extraction_node',
        partial(remind_task_extraction_node, llm=llm, remind_task_manager=remind_task_manager),
    )
    main_graph_builder.add_node('introspection_classifier_entry_node', introspection_classifier_entry_node)
    main_graph_builder.add_node('stream_final_response_node', partial(stream_final_response_node, llm=llm))

    main_graph_builder.add_edge(START, 'intent_classifier_entry_node')
    main_graph_builder.add_conditional_edges(
        'intent_classifier_entry_node',
        partial(intent_classifier_condition, llm=llm),
        {
            IntentClassification.ReactGraphAdapterNode: 'react_graph_adapter_node',
            IntentClassification.RemindTaskExtractNode: 'remind_task_extraction_node',
        },
    )
    main_graph_builder.add_edge('react_graph_adapter_node', 'introspection_classifier_entry_node')
    main_graph_builder.add_edge('remind_task_extraction_node', 'introspection_classifier_entry_node')
    main_graph_builder.add_conditional_edges(
        'introspection_classifier_entry_node',
        partial(introspection_classifier_condition, llm=llm),
        {
            IntrospectionClassification.IntentClassifierEntryNode: 'intent_classifier_entry_node',
            IntrospectionClassification.StreamFinalResponseNode: 'stream_final_response_node',
        },
    )
    main_graph_builder.add_edge('stream_final_response_node', END)
    return main_graph_builder
