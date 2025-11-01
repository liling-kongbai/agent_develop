from enum import Enum

from pydantic import BaseModel


# 图相关
class IntentClassification(str, Enum):
    '''枚举，意图类别'''

    ReactGraphAdapterNode = 'react_graph_adapter_node'  # ReAct 图适配器节点


class Intent(BaseModel):
    '''数据模型，意图'''

    intent: IntentClassification


class IntrospectionClassification(str, Enum):
    '''枚举，反思类别'''

    IntentClassifierEntryNode = 'intent_classifier_entry_node'  # 意图分类器入口节点
    AddFinalResponseNode = 'add_final_response_node'  # 添加最终回复节点


class Introspection(BaseModel):
    '''数据模型，反思'''

    introspection: IntrospectionClassification
