from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# 图相关
class IntentClassification(str, Enum):
    '''枚举，意图类别'''

    ReactGraphAdapterNode = 'react_graph_adapter_node'  # ReAct 图适配器节点
    RemindTaskExtractNode = 'remind_task_extract_node'  # 提醒任务提取节点


class Intent(BaseModel):
    '''数据模型，意图'''

    intent: IntentClassification


class IntrospectionClassification(str, Enum):
    '''枚举，反思类别'''

    IntentClassifierEntryNode = 'intent_classifier_entry_node'  # 意图分类器入口节点
    StreamFinalResponseNode = 'stream_final_response_node'  # 流式最终回复节点


class Introspection(BaseModel):
    '''数据模型，反思'''

    introspection: IntrospectionClassification


# 提醒任务相关
class RemindTask(BaseModel):
    '''
    提醒任务。
    用户指定的需要提醒的待办事项，一般有明确时间，如果没有明确时间，需要尝试推测一个合理的时间作为提醒任务的触发时间。
    提取提醒任务，并输出，程序将要到指定的时间提醒用户。
    '''

    description: str = Field(..., description='提醒任务的简短描述，例如：“明天上午九点开始写作业”。')
    due_time: datetime | None = Field(
        None,
        description='提醒任务的到期时间，例如：“2025-11-08T09:00:00”，请严格按照例子中的时间格式进行输出。如果没有明确时间信息，或者无法获得时间信息，可以尝试推测一个合理的时间作为提醒任务的触发时间；如果无法推测，则为 None',
    )
    context: str | None = Field(
        None,
        description='与提醒任务相关的简短的上下文信息，用于辅助提醒任务内容的简短的上下文总结信息，例如：“明天是假期第一天，计划明天先写作业再娱乐。”',
    )


class RemindTaskList(BaseModel):
    '''提醒任务列表'''

    tasks: list[RemindTask] = Field(
        ..., description='提醒任务列表，存放所有提取到的提醒任务。如果没有提醒任务，则返回一个空列表。'
    )
