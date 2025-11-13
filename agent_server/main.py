import logging
from asyncio import CancelledError, Event, Queue, create_task
from contextlib import asynccontextmanager
from traceback import format_exc

from fastapi import (  # 立即中断代码执行的特殊异常，由 FastAPI 自动转成包含指定状态码和错误详情的标准化 HTTP 响应
    FastAPI,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.responses import JSONResponse

from set_logger import set_logger
from src.server import Agent, Config
from src.server.assist import (
    ActivationRequest,
    LLMActivationRequest,
    StateChangeEvent,
    WebSocketConnectionManager,
    remind_task_scheduler,
)

# 日志相关
set_logger(log_path='agent_server.log')
logger = logging.getLogger(__name__)
logger.info('<main.py> 日志器启动')


# 辅助相关
websocket_connection_manager = WebSocketConnectionManager(logger)  # WebSocket 连接管理器实例
state_change_event_queue = Queue()  # 状态变化事件队列
remind_task_scheduler_wakeup_event = Event()  # 提醒任务调度器唤醒事件


async def state_change_event_consumer():
    '''状态变化事件消费者'''

    logger.info('<state_change_event_consumer> 状态变化事件消费者启动')
    while True:
        try:
            event: StateChangeEvent = await state_change_event_queue.get()
            message = {'type': event.state_name, 'payload': event.state}
            await websocket_connection_manager.broadcast_notification('liling', message)
            state_change_event_queue.task_done()
        except CancelledError:
            logger.info('<state_change_event_consumer> 状态变化事件消费者关闭')
            break
        except Exception:
            e = format_exc()
            logger.critical(f'<state_change_event_consumer> 状态变化事件消费者报错！！！\n{e}')
            await websocket_connection_manager.broadcast_notification(
                'liling',
                {
                    'type': 'occur_error',
                    'payload': f'<state_change_event_consumer> 状态变化事件消费者报错！！！\n{e}',
                },
            )
            raise


# 辅助 FastAPI 相关
config: Config | None = Config()
agent: Agent | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    '''异步上下文管理器，应用生命周期管理器，让 FastAPI 自动运行应用核心服务的启动和关闭'''

    try:
        state_change_event_consumer_task = create_task(state_change_event_consumer())

        global agent
        agent = Agent(config, state_change_event_queue, remind_task_scheduler_wakeup_event)
        await agent.init()

        global remind_task_scheduler_task
        remind_task_scheduler_task = create_task(
            remind_task_scheduler(
                agent._remind_task_manager,
                remind_task_scheduler_wakeup_event,
                websocket_connection_manager,
                'liling',
                logger,
            )
        )

        yield
    except Exception:
        e = format_exc()
        logger.critical(f'<lifespan> 启动 Agent 报错！！！\n{e}')
        await websocket_connection_manager.broadcast_notification(
            'liling',
            {
                'type': 'occur_error',
                'payload': f'<lifespan> 启动 Agent 报错！！！\n{e}',
            },
        )
        raise
    finally:
        try:
            logger.info('<lifespan> 清理 Agent')
            if agent:
                await agent.clean()
        except CancelledError:
            logger.warning('<lifespan> 清理 Agent 被取消，此动作应该正常！')
        except Exception:
            e = format_exc()
            logger.critical(f'<lifespan> 清理 Agent！！！\n{e}')
            await websocket_connection_manager.broadcast_notification(
                'liling',
                {
                    'type': 'occur_error',
                    'payload': f'<lifespan> 清理 Agent！！！\n{e}',
                },
            )
            raise

        try:
            if 'state_change_event_consumer_task' in locals() and not state_change_event_consumer_task.done():
                state_change_event_consumer_task.cancel()
                await state_change_event_consumer_task
                logger.info('<lifespan> 清理状态变化事件消费者任务完成')

            if 'remind_task_scheduler_task' in globals() and not remind_task_scheduler_task.done():
                remind_task_scheduler_task.cancel()
                await remind_task_scheduler_task
                logger.info('<lifespan> 清理提醒任务调度器任务完成')
        except CancelledError:
            logger.warning('<lifespan> 清理任务被取消，此动作应该正常！')
        except Exception:
            e = format_exc()
            logger.critical(f'<lifespan> 清理任务报错！！！\n{e}')
            await websocket_connection_manager.broadcast_notification(
                'liling',
                {
                    'type': 'occur_error',
                    'payload': f'<lifespan> 清理任务报错！！！\n{e}',
                },
            )
            raise


app = FastAPI(lifespan=lifespan)  # 构建 FastAPI 应用实例


# 辅助 FastAPI 相关
@app.exception_handler(Exception)
async def exception_handler(request: Request, exc: Exception) -> JSONResponse:
    '''异常处理器'''

    e = format_exc()
    logger.error(f'{request.url.path} 报错！！！\n{e}')
    await websocket_connection_manager.broadcast_notification(
        'liling', {'type': 'occur_error', 'payload': f'{request.url.path} 报错！！！\n{e}'}
    )
    return JSONResponse(
        f'{request.url.path} 报错！！！\n{e}',
        status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


# 路由操作相关
@app.post('/activate_llm')
async def activate_llm(request: LLMActivationRequest):
    if not agent:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, 'Agent 未初始化！！！')

    platform = request.platform
    llm = request.llm
    await agent.activate_llm(platform, llm)
    return {'message': f'{platform} 的 {llm} 已激活'} if not platform or not llm else {'message': 'LLM 已清理'}


@app.post('/activate_mcp_client')
async def activate_mcp_client(request: ActivationRequest):
    if not agent:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, 'Agent 未初始化！！！')

    activation = request.activation
    await agent.activate_mcp_client(activation)
    return (
        {'message': '多服务器 MCP 客户端已激活并加载工具'}
        if activation
        else {'message': '多服务器 MCP 客户端和工具已清理'}
    )


@app.post('/activate_gpt_sovits')
async def activate_gpt_sovits(request: ActivationRequest):
    if not agent:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, 'Agent 未初始化！')

    activation = request.activation
    await agent.activate_gpt_sovits(activation)
    return {'message': 'GPT_SoVITS 已激活'} if activation else {'message': 'GPT_SoVITS 已关闭并清理'}


@app.post('/load_chat_history')
async def load_chat_history():
    if not agent:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, 'Agent 未初始化！！！')

    chat_history = await agent.load_chat_history()
    return {'chat_history': chat_history}


@app.post('/load_chat/{thread_id}')
async def load_chat(thread_id: str):
    if not agent:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, 'Agent 未初始化！！！')

    chat = await agent.load_chat(thread_id)
    return {'chat': chat}


@app.websocket('/ws/notification/{user_id}')
async def websocket_notification(user_id: str, websocket: WebSocket):
    if not agent:
        await websocket.close(
            status.HTTP_503_SERVICE_UNAVAILABLE, 'Agent 未初始化！！！'
        )  # 服务器端 WebSocket 终止连接，关闭握手，允许发送状态码和原因
        return

    await websocket.accept()  # 完成服务器端 WebSocket 握手，将连接从 HTTP 升级并授权双向通信
    websocket_connection_manager.connect_notification('liling', websocket)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.error('<websocket_notification> WebSocket 连接关闭！！！')
    except Exception:
        try:
            e = format_exc()
            logger.critical(f'<websocket_notification> WebSocket 通知报错！！！\n{e}')
            await websocket.send_json(
                {'type': 'occur_error', 'payload': f'<websocket_notification> WebSocket 通知报错！！！\n{e}'}
            )
            await websocket.close(
                status.WS_1011_INTERNAL_ERROR, f'<websocket_notification> WebSocket 通知报错！！！\n{e}'
            )
        except Exception:
            e = format_exc()
            logger.critical(f'<websocket_notification> WebSocket 报错报错！！！{e}')
    finally:
        websocket_connection_manager.disconnect_notification('liling', websocket)


@app.websocket('/ws/chat/{thread_id}')
async def websocket_chat(thread_id: str, websocket: WebSocket):
    if not agent:
        await websocket.close(status.HTTP_503_SERVICE_UNAVAILABLE, 'Agent 未初始化！！！')
        return

    await websocket.accept()
    websocket_connection_manager.connect_chat(thread_id, websocket)

    await agent.reset_chat_state()

    agent.current_thread_id = thread_id

    await agent._state_change_event_queue.put(StateChangeEvent('input_ready', True))

    try:
        while True:
            user_content = await websocket.receive_text()
            create_task(agent.chat(user_content, websocket))
    except WebSocketDisconnect:
        logger.error('<websocket_chat> WebSocket 连接关闭！！！')
    except Exception:
        try:
            e = format_exc()
            logger.critical(f'<websocket_chat> WebSocket 对话报错！！！\n{e}')
            await websocket.send_json(
                {'type': 'occur_error', 'payload': f'<websocket_chat> WebSocket 对话报错！！！\n{e}'}
            )
            await websocket.close(status.WS_1011_INTERNAL_ERROR, f'<websocket_chat> WebSocket 对话报错！！！\n{e}')
        except Exception:
            e = format_exc()
            logger.critical(f'<websocket_chat> WebSocket 报错报错！！！{e}')
    finally:
        websocket_connection_manager.disconnect_chat(thread_id, websocket)
