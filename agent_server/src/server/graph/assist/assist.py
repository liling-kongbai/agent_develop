from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.runnables.base import RunnableSequence

from .base_structured_output_extractor import BaseStructuredOutputExtractor
from .type import Intent, IntentClassification, Introspection, IntrospectionClassification, RemindTaskList


# 主图相关
class IntentClassifier(BaseStructuredOutputExtractor):
    '''意图分类器'''

    OUTPUT_SCHEMA = Intent
    SYSTEM_PROMPT = '''\
        你是一个专业的对话意图路由器。你的任务是分析对话历史中的所有消息，并将其意图精准地路由到正确的处理节点。
        下面使用 <<< 和 >>> 包裹的是对话列表，对话列表中的内容是用户和你的对话。
        <<<
            {messages}
        >>>
        请分析对话列表中的所有消息，“尤其”是用户的“最新的一条消息”，然后将用户接下来的意图分为以下之一：
            1. 如果只是普通的对话和聊天，请返回{IntentClassification_ReactGraphAdapterNode}；
            2. 如果是有关提醒的任务，指令，意图等，类似定时提醒的情况，请返回{IntentClassification_RemindTaskExtractNode}。
        请注意，按照要求的格式返回相关的内容，不要输出错误的格式，不要输出错误的内容。
        请严格按照 JSON 格式返回，不要包含任何额外的解释或文本。
        '''

    def _get_partial_variables(self) -> dict[str, Any]:
        return {
            'IntentClassification_ReactGraphAdapterNode': IntentClassification.ReactGraphAdapterNode.value,
            'IntentClassification_RemindTaskExtractNode': IntentClassification.RemindTaskExtractNode.value,
        }


def create_intent_classifier_chain(llm: BaseChatModel) -> RunnableSequence:
    '''创建意图分类器链'''

    return IntentClassifier(llm).get_extractor_chain()


class RemindTaskExtractor(BaseStructuredOutputExtractor):
    '''提醒任务提取器'''

    OUTPUT_SCHEMA = RemindTaskList
    SYSTEM_PROMPT = '''\
        你是一个高度专业、极其精确的**提醒任务提取 AI**。你的职责是分析对话历史，并严格识别其中包含的**待办事项或定时提醒**。
        ---
        **对话历史：**
        {messages}
        ---
        **当前时间：**
        {time}
        ---
        **核心提取与推断规则（请严格遵守）：**
        1. **任务判断：** 只有明确要求“提醒”、“记住”、“帮我跟进”、“下次...”等具有**未来执行意图**的语句才视为任务。普通的问答、聊天、或当前即时操作请求（如“现在帮我查天气”）不应被提取。
        2. **时间推断（关键）：**
           a. **时区基准：** 所有时间的推算都必须基于 **北京时间（东八区）**。
           b. **格式要求：** 必须将所有相对时间描述（如“明天早上 9 点”、“下周一”）准确地转换为 **不带时区的 ISO 8601 格式**，例如 **"2025-11-13T14:30:00"**。
           c. **日期完整性：** 如果用户只提到时间（例如“下午三点”），你必须推断为**最近的、最合理的**那个下午三点（例如今天下午三点，如果时间已过，则为明天下午三点），并补全完整日期。
           d. **不可推断性：** 如果任务没有时间信息，且无法根据上下文合理推断出时间（例如“等我有空了提醒我”），你应该尽量尝试推测一个比较可能的时间，否则则将 `due_time` 字段设置为 **null**。
        3. **上下文总结：** `context` 字段必须是与该提醒任务相关的**简短的、可独立阅读的**上下文总结。
        4. **空列表处理：** 如果在对话中没有检测到任何符合上述标准的提醒或待办任务，请返回一个**空列表**。
        ---
        **请严格按照**你的输出模式的 JSON 结构**返回任务列表**，不要输出任何额外的解释、Markdown 格式或任何非 JSON 文本。
    '''


def create_remind_task_extractor_chain(llm: BaseChatModel) -> RunnableSequence:
    '''创建提醒任务提取器链'''

    return RemindTaskExtractor(llm).get_extractor_chain()


class IntrospectionClassifier(BaseStructuredOutputExtractor):
    '''反思分类器'''

    OUTPUT_SCHEMA = Introspection
    SYSTEM_PROMPT = '''\
        你是一个专业的 AI 回复评估员。你的任务是基于对话历史，对 AI 助手的回复草稿进行多维度打分，并根据你的分数做出最终决策。

        **对话历史:**
        <<<
        {messages}
        >>>

        **AI 助手的回复草稿:**
        <<<
        {response_draft}
        >>>

        **评估指南:**
        请从以下维度进行 1 - 5 分的评分（1=差，3=合格，5=优秀）。
            1. **正确性（Correctness）**: 回复是否准确、真实地解决了用户的核心问题？
            2. **完整性（Completeness）**: 回复是否涵盖了用户问题的所有方面？
            3. 如果只是普通的打招呼或聊天对话，只要没有出现什么问题，就不需要再一次进行回复的生成，两个维度可以直接给 3 分以上。
            4. 如果回复草稿是“成功记录了提醒任务或待办事项”相关的内容，说明提醒任务提取成功且正确，就不需要再一次进行回复的生成，两个维度可以直接给 3 分以上。

        **决策指南:**
        - 如果 **正确性** 或 **完整性** 评分 **都低于 3 分**，说明回复有重大缺陷，最终决策应该输出 **'{IntrospectionClassification.IntentClassifierEntryNode}'** (重试)。
        - 如果 **正确性** 和 **完整性** 评分 **都达到或超过 3 分**，说明回复质量足够高，最终决策应该输出 **'{IntrospectionClassification.StreamFinalResponseNode}'** (接受)。

        请严格按照格式要求返回，不要包含任何其他解释。请注意，按照要求的格式返回相关的内容，不要输出错误的格式，不要输出错误的内容。
        '''

    def _get_partial_variables(self) -> dict[str, Any]:
        return {
            'IntrospectionClassification_IntentClassifierEntryNode': IntrospectionClassification.IntentClassifierEntryNode.value,
            'IntrospectionClassification_StreamFinalResponseNode': IntrospectionClassification.StreamFinalResponseNode.value,
        }


def create_introspection_classifier_chain(llm: BaseChatModel) -> RunnableSequence:
    '''创建反思分类器链'''

    return IntrospectionClassifier(llm).get_extractor_chain()
