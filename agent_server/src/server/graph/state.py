from typing import Annotated  # 类型可加元数据类型，在类型注解中添加额外元数据

from langchain_core.messages import AIMessage, BaseMessage
from langgraph.graph.message import add_messages  # 追加合并两个消息列表或通过 id 更新现有消息
from pydantic import BaseModel


class MainState(BaseModel):
    '''主图状态'''

    system_prompt: str
    user_name: str
    ai_name: str
    chat_language: str
    messages: Annotated[list[BaseMessage], add_messages]
    response_draft: AIMessage | None
    introspection_count: int


class ReActState(BaseModel):
    '''ReAct 图状态'''

    system_prompt: str
    user_name: str
    ai_name: str
    chat_language: str
    messages: Annotated[list[BaseMessage], add_messages]
