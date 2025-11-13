import logging
from asyncio import Event, Queue, create_task, to_thread
from pathlib import Path
from textwrap import dedent

from fastapi import WebSocket
from langchain_core.messages.ai import AIMessageChunk
from langchain_core.messages.human import HumanMessage
from langchain_core.runnables.config import RunnableConfig
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_ollama import OllamaEmbeddings
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres import AsyncPostgresStore
from langgraph.store.postgres.base import PostgresIndexConfig
from langmem import create_memory_store_manager
from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from .assist import (
    DurableReflectionExecutor,
    EpisodeMemory,
    RemindTaskManager,
    StateChangeEvent,
    chat_title_executor,
    connect_deepseek_llm,
    connect_ollama_llm,
)
from .config import Config, settings
from .graph.graph import create_main_graph_builder
from .graph.node import chat_node
from .tts.GPT_SoVITS import GPT_SoVITS

# 日志相关
logger = logging.getLogger(__name__)


class Agent:
    '''智能体'''

    QUERY_SQL = dedent(
        '''\
        WITH LatestCheckpoints AS (
            SELECT thread_id, checkpoint_id, metadata,
                ROW_NUMBER() OVER (PARTITION BY thread_id, checkpoint_ns ORDER BY checkpoint_id DESC) as rn
            FROM checkpoints
            WHERE checkpoint_ns = ''
        )
        SELECT thread_id, metadata->>'title' as title
        FROM LatestCheckpoints
        WHERE rn = 1
        ORDER BY checkpoint_id DESC
        '''
    )

    def __init__(self, config: Config, state_change_event_queue: Queue, remind_task_scheduler_wakeup_event: Event):
        self._config: Config | None = config

        # 状态相关
        self._state_change_event_queue: Queue | None = state_change_event_queue
        self._graph_readied: bool = False
        self._llm_activated: bool = False

        # 提醒任务相关
        self._remind_task_scheduler_wakeup_event: Event | None = remind_task_scheduler_wakeup_event

        # 对话标题相关
        self._chat_title_executor_set: set[str] | None = set()

        # 初始化相关
        self._init_variable_about_postgres()
        self._init_variable_about_graph()
        self._init_variable_about_episode_memory()
        self._init_variable_about_llm()
        self._init_variable_about_mcp_client()
        self._init_variable_about_gpt_sovits()

    # 初始化相关
    async def init(self):
        '''初始化，初始化 Agent 启动所需的资源和动作'''

        try:
            logger.info('<init> 初始化')
            await self._init_postgres()
            await self._compile_graph()
            logger.info('<init> 初始化完成')
        except Exception:
            raise

    def _init_variable_about_postgres(self):
        self._postgres_connection_string = settings.POSTGRES_CONNECTION_STRING  # 数据库连接字符串

        self._postgres_index_config = None  # 数据库索引配置
        self._postgres_connection_pool = None  # 数据库连接池
        self._postgres = None  # 数据库
        self._async_postgres_saver = None  # 异步数据库检查点保存器

    async def _init_postgres(self):
        '''初始化 Postgres 数据库'''

        try:
            logger.info('<_init_postgres> 初始化 Postgres 数据库')
            logger.info('<_init_postgres> 初始化数据库索引配置')
            self._embedding_model = OllamaEmbeddings(model='bge-m3:latest')
            self._postgres_index_config: PostgresIndexConfig = {
                'dims': 1024,  # 向量维度，嵌入模型输出向量的维度
                'embed': self._embedding_model,
                'fields': [
                    'content.observation',
                    'content.thought',
                    'content.action',
                    'content.result',
                ],  # 文本内容提取规则，提取 content 对象下的字段并拼接用于生成向量
                'ann_index_config': {
                    'kind': 'hnsw',
                    'vector_type': 'vector',
                },  # 近似最近邻索引配置，近似最近邻检索，索引类型，向量类型
                'distance_type': 'cosine',  # 距离类型，距离度量算法，'l2', 'inner_product', 'cosine'
            }

            logger.info('<_init_postgres> 初始化数据库准备所需动作')
            async with await AsyncConnection.connect(self._postgres_connection_string, autocommit=True) as conn:
                temporary_postgres = AsyncPostgresStore(conn, index=self._postgres_index_config)
                await temporary_postgres.setup()
                await AsyncPostgresSaver(conn).setup()
                await RemindTaskManager.setup(conn)

            logger.info('<_init_postgres> 初始化数据库连接池')
            self._postgres_connection_pool = AsyncConnectionPool(
                self._postgres_connection_string, min_size=3, max_size=5, open=False
            )
            await self._postgres_connection_pool.open()

            logger.info('<_init_postgres> 创建数据库')
            self._postgres = AsyncPostgresStore(self._postgres_connection_pool, index=self._postgres_index_config)

            logger.info('<_init_postgres> 初始化异步数据库检查点保存器')
            self._async_postgres_saver = AsyncPostgresSaver(self._postgres_connection_pool)

            logger.info('<_init_postgres> 初始化 Postgres 数据库完成')
        except Exception:
            raise

    def _init_variable_about_graph(self):
        self.current_thread_id = None
        self.user_id = 'liling'

        self._graph = None

        # 提醒任务相关
        self._remind_task_manager: RemindTaskManager | None = None  # 提醒任务管理器

    async def _compile_graph(self):
        '''编译图'''

        try:
            logger.info('<_compile_graph> 编译图')
            if self._async_postgres_saver:
                self._remind_task_manager = RemindTaskManager(
                    self._postgres_connection_pool, self._remind_task_scheduler_wakeup_event
                )

                graph_builder = await create_main_graph_builder(
                    chat_node, self._llm_bind_tools, self._remind_task_manager, self._mcp_tools
                )
                self._graph = graph_builder.compile(self._async_postgres_saver)

                self._graph_readied = True
                await self._ready_check()
                logger.info('<_compile_graph> 编译图完成')
            else:
                raise NameError('''name '_async_postgres_saver(异步 Postgres 数据库检查点保存器)' is not defined''')
        except:
            raise

    def _init_variable_about_episode_memory(self):
        self._after_seconds = 60 * 3
        self._episode_memory_count: int = 0  # 情景记忆计数
        self._is_first_handle_episode_memory = True

        self._memory_store_manager = None  # 记忆存储管理器
        self._durable_reflection_executor = None  # 持久化反思执行器

    async def _init_episode_memory(self):
        '''初始化情景记忆'''

        try:
            logger.info('<_init_episode_memory> 初始化情景记忆')
            logger.info('<_init_episode_memory> 创建记忆存储管理器')
            self._memory_store_manager = create_memory_store_manager(
                self._llm,
                schemas=[EpisodeMemory],
                namespace=('memories', self.user_id),
                store=self._postgres,
            )

            logger.debug('<_init_episode_memory> 创建持久反思化执行器')
            self._durable_reflection_executor = await DurableReflectionExecutor.ainit(
                self._memory_store_manager, self._postgres
            )
            logger.info('<_init_episode_memory> 初始化情景记忆完成')
        except:
            raise

    # 功能相关
    def _init_variable_about_llm(self):
        self._llm_connectors = {'ollama': connect_ollama_llm, 'deepseek': connect_deepseek_llm}

        self._embedding_model = None  # 嵌入模型，目前定死
        self._llm = None
        self._llm_bind_tools = self._llm

    async def activate_llm(self, platform: str, llm: str):
        '''激活 LLM，创建或清理 LLM'''

        self._llm_bind_tools = None
        self._llm = None
        self._llm_activated = False

        if not platform or not llm:  # 清理
            logger.info('<activate_llm> LLM 已清理')
            return

        try:  # 创建
            logger.info('<activate_llm> 创建 LLM')
            if platform in self._llm_connectors:
                self._llm = await self._llm_connectors[platform](llm, None, None, None)

                self._llm_activated = True
                await self._update_tools_bind()
                await self._ready_check()
                logger.info('<activate_llm> 创建 LLM 完成')
        except Exception:
            raise

    def _init_variable_about_mcp_client(self):
        self._multi_server_mcp_client = None
        self._mcp_tools = []

    async def activate_mcp_client(self, activation: bool):
        '''激活 MCP 客户端，创建多服务器 MCP 客户端并加载工具'''

        try:
            if activation and not self._multi_server_mcp_client:
                logger.info('<activate_mcp_client> 创建多服务器 MCP 客户端')

                project_path = Path(__file__).resolve().parents[3]
                mcp_server_cwd = project_path / 'mcp_server'
                mcp_server_script_path = mcp_server_cwd / 'src' / 'mcp_server' / 'mcp_server.py'

                if not mcp_server_script_path.exists():
                    e = f'<activate_mcp_client> MCP 服务器脚本不存在，请检查: {mcp_server_script_path}'
                    logger.error(e)
                    raise FileNotFoundError(e)

                self._multi_server_mcp_client = MultiServerMCPClient(
                    {
                        'test': {
                            'transport': 'stdio',
                            'command': 'uv',
                            'args': [
                                'run',
                                str(mcp_server_script_path),
                            ],
                            'cwd': str(mcp_server_cwd),
                        }
                    }
                )

                logger.info('<activate_mcp_client> 获取多服务器 MCP 客户端工具')
                self._mcp_tools = await self._multi_server_mcp_client.get_tools()
            elif not activation and self._multi_server_mcp_client:
                logger.info('<activate_mcp_client> 清理多服务器 MCP 客户端和工具')
                self._mcp_tools = []
                self._multi_server_mcp_client = None

            await self._update_tools_bind()
        except Exception:
            raise

    def _init_variable_about_gpt_sovits(self):
        self._gpt_sovits = None  # 没有写流式功能，还能改造，还能更快

    async def activate_gpt_sovits(self, activation: bool):
        '''激活 GPT_SoVITS，创建并启动，关闭并清理'''

        try:
            if activation and not self._gpt_sovits:
                self._gpt_sovits = GPT_SoVITS(self._config)
                await self._gpt_sovits.start()
            elif not activation and self._gpt_sovits:
                await self._gpt_sovits.stop()
                self._gpt_sovits = None
        except Exception:
            raise

    async def load_chat_history(self):
        '''加载对话历史'''

        chat_history = []
        try:
            async with self._postgres_connection_pool.connection() as conn:
                async with conn.cursor(row_factory=dict_row) as cur:
                    await cur.execute(self.QUERY_SQL)
                    rows = await cur.fetchall()
                    for row in rows:
                        chat_history.append({'thread_id': row['thread_id'], 'title': row['title']})
            return chat_history
        except Exception:
            raise

    async def load_chat(self, thread_id: str):
        '''加载对话'''

        try:
            await self._state_change_event_queue.put(StateChangeEvent('input_ready', False))

            self.current_thread_id = thread_id
            config = RunnableConfig(
                configurable={
                    'thread_id': self.current_thread_id,
                    'user_id': self.user_id,
                }
            )

            checkpoint_tuple = await self._async_postgres_saver.aget_tuple(config)
            messages = checkpoint_tuple.checkpoint['channel_values']['messages']
            chat = []
            for message in messages:
                is_user = isinstance(message, HumanMessage)
                chat.append({'is_user': is_user, 'content': message.content})
            return chat
        except Exception:
            raise
        finally:
            await self._state_change_event_queue.put(StateChangeEvent('input_ready', True))

    async def chat(self, user_content: str, websocket: WebSocket):
        '''对话'''

        await self._state_change_event_queue.put(StateChangeEvent('input_ready', False))

        chat_title_executor_activated = False

        episode_memory = ''
        config = RunnableConfig(
            configurable={
                'thread_id': self.current_thread_id,
                'user_id': self.user_id,
            }
        )
        try:
            # 对话标题相关
            metadata_to_save = {}
            checkpoint_tuple = await self._async_postgres_saver.aget_tuple(config)
            is_new_chat = checkpoint_tuple is None

            if is_new_chat:
                metadata_to_save = {'title': '新对话', 'title_generated': False, 'chat_round': 1}
            else:
                metadata_to_save = checkpoint_tuple.metadata.copy()
                if not metadata_to_save.get('title_generated', False):
                    current_chat_round = metadata_to_save.get('chat_round', 0)
                    new_count = current_chat_round + 1
                    metadata_to_save['chat_round'] = new_count
                    if new_count >= 3:
                        chat_title_executor_activated = True

            config_with_metadata = config.copy()
            config_with_metadata['metadata'] = metadata_to_save

            # 情景记忆相关
            episodes = await self._postgres.asearch(('memories', self.user_id), query=user_content, limit=2)
            if episodes:
                for i, episode in enumerate(episodes):
                    episode_value = episode.value['content']
                    episode_memory += dedent(
                        f'''\
                        情景记忆 {self._episode_memory_count + 1} :
                            观察：{episode_value['observation']}
                            思考：{episode_value['thought']}
                            行动：{episode_value['action']}
                            结果：{episode_value['result']}\n
                        '''
                    )
                    self._episode_memory_count += 1
                if self._is_first_handle_episode_memory:
                    system_prompt = (
                        self._config.state['system_prompt'] + self._config.episode_memeory_prompt + episode_memory
                    )
                    self._is_first_handle_episode_memory = False
                else:
                    system_prompt = self._config.state['system_prompt'] + episode_memory
            else:
                system_prompt = self._config.state['system_prompt']

            current_state = {
                'system_prompt': system_prompt,
                'user_name': self._config.state['user_name'],
                'ai_name': self._config.state['ai_name'],
                'chat_language': self._config.state['chat_language'],
                'messages': HumanMessage(user_content),
                'response_draft': None,
                'introspection_count': 0,
            }

            # 图运行相关
            async for event in self._graph.astream_events(current_state, config_with_metadata, version='v1'):
                event_name = event['name']
                event_type = event['event']

                if event_name in ['LangGraph', '__start__', '__end__']:
                    continue

                if event_type == 'on_chain_start':
                    event_message = f'{event_name} 正在运行 --->\n'
                    await websocket.send_json({'type': 'graph_operate_log', 'payload': event_message})
                    logger.debug(event_message)
                elif event_type == 'on_chain_end':
                    node_output = event['data']['output']
                    node_message = f'{event_name} 运行完毕 --->\n'
                    if isinstance(node_output, dict) and node_output:
                        if event_name == 'stream_final_response_node':
                            node_message += '正在生成流式回复···\n'
                        else:
                            for key, value in node_output.items():
                                value = repr(value)
                                if len(value) > 50:
                                    value = value[:50] + '···'
                                node_message += f'{key}: {value}\n'
                    else:
                        node_message += ' 无输出 \n'
                    await websocket.send_json({'type': 'graph_operate_log', 'payload': node_message})
                    logger.debug(node_message)
                elif event_type == 'on_chain_stream' and event_name == 'stream_final_response_node':
                    chunk = event['data']['chunk']
                    if isinstance(chunk, dict) and 'chunk' in chunk:
                        ai_message_chunk = chunk['chunk']
                        if isinstance(ai_message_chunk, AIMessageChunk):
                            chunk_content = ai_message_chunk.content
                            if chunk_content:
                                await websocket.send_json({'type': 'ai_message_chunk', 'payload': chunk_content})
                                if self._gpt_sovits:
                                    await self._gpt_sovits.put_text_in_queue(chunk_content)

            if self._gpt_sovits:
                await self._gpt_sovits.emit_text_final_signal()

            # 对话标题相关
            if is_new_chat:
                await self._state_change_event_queue.put(StateChangeEvent('chat_title_generated', True))

            if chat_title_executor_activated:
                thread_id = self.current_thread_id
                if thread_id not in self._chat_title_executor_set:
                    self._chat_title_executor_set.add(thread_id)

                    async def _chat_title_executor_task():
                        try:
                            await chat_title_executor(
                                checkpoint_tuple, self._llm, self._postgres_connection_pool, thread_id
                            )
                            await self._state_change_event_queue.put(StateChangeEvent('chat_title_generated', True))
                        except Exception:
                            raise
                        finally:
                            self._chat_title_executor_set.remove(thread_id)

                    create_task(_chat_title_executor_task())

            # 情景记忆相关
            if self._durable_reflection_executor:
                final_state = await self._graph.aget_state(config)
                messages = final_state.values['messages']
                serializable_messages = [message.dict() for message in messages]
                await self._durable_reflection_executor.asubmit(
                    {'messages': serializable_messages},
                    config=config,
                    after_seconds=self._after_seconds,
                )

        except Exception:
            raise
        finally:
            await self._state_change_event_queue.put(StateChangeEvent('input_ready', True))

    async def reset_chat_state(self):
        '''重置对话状态'''

        logger.info('<reset_chat_state> 重置对话状态')
        self._episode_memory_count = 0
        self._is_first_handle_episode_memory = True

    # 辅助相关
    async def _ready_check(self):
        '''准备检查，检查图是否准备，LLM 是否激活，情景记忆是否工作'''

        if self._graph_readied and self._llm_activated:
            if not self._durable_reflection_executor:
                await self._init_episode_memory()

    async def _update_tools_bind(self):
        '''更新工具绑定'''

        if self._mcp_tools:
            self._llm_bind_tools = self._llm.bind_tools(self._mcp_tools)
        else:
            self._llm_bind_tools = self._llm

        await self._compile_graph()

    async def clean(self):
        try:
            await self._state_change_event_queue.put(StateChangeEvent('input_ready', False))

            if self._gpt_sovits:
                await self.activate_gpt_sovits(False)
            if self._multi_server_mcp_client:
                await self.activate_mcp_client(False)
            if self._llm_activated:
                await self.activate_llm('', '')

            if self._durable_reflection_executor:
                logger.info('<clean> 关闭并清理持久化反思执行器')
                await to_thread(self._durable_reflection_executor.shutdown, wait=True, cancel_futures=True)
                self._durable_reflection_executor = None

            if self._memory_store_manager:
                logger.info('<clean> 清理记忆存储管理器')
                self._memory_store_manager = None

            if self._graph_readied:
                logger.info('<clean> 清理图')
                self._graph_readied = False
                self._remind_task_manager = None
                self.graph = None

            if self._async_postgres_saver:
                logger.info('<clean> 清理异步数据库检查点保存器')
                self._async_postgres_saver = None

            if self._postgres:
                logger.debug('<clean> 清理数据库')
                self._postgres = None

            if self._postgres_connection_pool:
                logger.debug('<clean> 关闭并清理数据库连接池')
                await self._postgres_connection_pool.close()  # 安全地关闭所有数据库连接并清理资源，确保程序干净退出
                self._postgres_connection_pool = None

            if self._postgres_index_config:
                logger.debug('<clean> 清理数据库索引配置')
                self._postgres_index_config = None
                self._embedding_model = None

            logger.debug('<clean> 清理完毕')
        except:
            raise
