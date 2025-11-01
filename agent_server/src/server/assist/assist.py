from os import getenv
from textwrap import dedent

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_deepseek import ChatDeepSeek
from langchain_ollama import ChatOllama
from langgraph.checkpoint.base import CheckpointTuple


# LLM 相关
async def connect_ollama_llm(model, base_url, temperature, num_predict):
    '''连接 Ollama 的 LLM'''

    params = {'model': model}
    params['base_url'] = base_url if base_url else r'http://localhost:11434'
    if temperature:
        params['temperature'] = temperature
    if num_predict:
        params['num_predict'] = num_predict
    llm = ChatOllama(**params)
    return llm


async def connect_deepseek_llm(model, api_key, temperature, max_tokens):
    '''连接 DeepSeek 的 LLM'''

    params = {'model': model}
    params['api_key'] = api_key if api_key else getenv('DEEPSEEK_API_KEY')
    if temperature:
        params['temperature'] = temperature
    if max_tokens:
        params['max_tokens'] = max_tokens
    llm = ChatDeepSeek(**params)
    return llm


# 对话历史相关
async def chat_title_executor(checkpoint_tuple: CheckpointTuple, llm: BaseChatModel, connection_pool, thread_id):
    '''对话标题处理器'''

    try:
        messages = checkpoint_tuple.checkpoint['channel_values']['messages']
        contents = '\n'.join([f'{message.type}: {message.content}' for message in messages[:]])

        chat_title_executor_prompt = dedent(
            f'''\
            下面使用 <<< 和 >>> 包裹的是对话列表，对话列表中的内容是用户和你的对话。
            <<<
                {contents}
            >>>
            请根据对话列表中的内容，生成一个非常简短且精炼的中文标题，不超过 15 个字。
            标题需要准确概括对话的核心主题。
            请以纯文本的形式直接输出生成的中文标题，不要包含任何多余的解释，符号或格式。
            '''
        )
        response = await llm.ainvoke(chat_title_executor_prompt)
        title = response.content.strip()
        if not title:
            return

        UPDATE_SQL = dedent(
            '''\
            UPDATE checkpoints
            SET metadata = jsonb_set(
                jsonb_set(
                    metadata,
                    '{title}',
                    to_jsonb(%s::text),
                    true
                ),
                '{title_generated}',
                'true'::jsonb,
                true
            )
            WHERE thread_id = %s
            '''
        )
        async with connection_pool.connection() as conn:
            async with conn.cursor() as cur:
                await conn.execute(UPDATE_SQL, (title, thread_id))
            await conn.commit()
    except Exception:
        raise
