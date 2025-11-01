import asyncio
import logging
from asyncio import CancelledError, Queue, TimeoutError, create_task, to_thread, wait_for
from re import UNICODE, compile, split, sub

# 将协程包装成任务并排入事件循环中执行
import numpy as np
from aiohttp import ClientSession  # 创建和管理异步 HTTP 会话，允许以异步方式发送 HTTP 请求并处理响应
from sounddevice import OutputStream  # 创建音频输出流，将音频数据发送到音频设备进行播放

logger = logging.getLogger(__name__)


class GPT_SoVITS:
    '''GPT_SoVITS 代理'''

    _TEXT_FINAL_SENTINEL = object()
    _AUDIO_SENTINEL = object()

    _PATTERN = compile(
        '['
        '\U0001f600-\U0001f64f'
        '\U0001f300-\U0001f5ff'
        '\U0001f680-\U0001f6ff'
        '\U0001f1e0-\U0001f1ff'
        '\U00002702-\U000027b0'
        '\U000024c2-\U0001f251'
        '\U0001f926-\U0001f937'
        '\U00010000-\U0010ffff'
        '\u2640-\u2642'
        '\u2600-\u2b55'
        '\u200d'
        '\u23cf'
        '\u23e9'
        '\u231a'
        '\ufe0f'
        '\u3030'
        ']+',
        flags=UNICODE,
    )
    _PUNCTUATION = '[,.?!:，。？！：]'

    def __init__(self, config):
        # 配置相关
        self._config = config
        self._base_url = f'http://{self._config.host}:{self._config.port}'
        self._params = {
            'text_lang': 'zh',
            'ref_audio_path': self._config.ref_audio_path,
            'prompt_lang': 'zh',
            'prompt_text': self._config.prompt_text,
            'text_split_method': self._config.text_split_method,
            'speed_factor': self._config.speed_factor,
            'streaming_mode': True,
            'sample_steps': self._config.sample_steps,
        }

        self._sample_rate = 48000
        self._channels = 1

        # 状态相关
        self._is_running = False
        self._is_skip_wav_header = False  # 标记是否已跳过 WAV 头部

        # 缓冲相关
        self._buffer_size = 19200  # 缓冲区大小

        self._text_buffer = ''
        self._audio_buffer = b''

        # 功能相关
        self._timeout_sec = 0.5

        self._session = None
        self._audio_output_stream = None

        # 任务相关
        self._text_queue = Queue()
        self._audio_chunk_queue = Queue()

        self._tasks = []

    # 初始化相关
    async def start(self):
        '''启动 GPT_SoVITS 代理，初始化状态，资源，动作'''

        if self._is_running:
            return
        logger.info('<start> 启动 GPT_SoVITS 代理 ··· ')
        self._is_running = True

        try:
            self._session = ClientSession()

            await self._set_model()

            logger.info('<start> 初始化音频输出流 ··· ')
            self._audio_output_stream = OutputStream(
                samplerate=self._sample_rate, channels=self._channels, dtype='int16'
            )
            self._audio_output_stream.start()

            self._tasks.append(create_task(self._stream_tts_worker()))
            self._tasks.append(create_task(self._audio_play_worker()))
            logger.info('<start> 启动 GPT_SoVITS 代理成功')
        except Exception:
            await self.stop()
            raise

    # 辅助相关
    async def _set_model(self):
        '''设置模型'''

        try:
            async with self._session.get(
                f'{self._base_url}/set_gpt_weights', params={'weights_path': self._config.gpt_weights_path}
            ) as response:  # 设置 GPT 模型
                response.raise_for_status()  # 检查 HTTP 响应状态码
                logger.info(
                    f'设置 GPT 模型成功: {await response.text()}'
                )  # 读取服务器返回的完整响应正文并尝试解码为字符串

            async with self._session.get(
                f'{self._base_url}/set_sovits_weights', params={'weights_path': self._config.sovits_weights_path}
            ) as response:  # 设置 Sovits 模型
                response.raise_for_status()
                logger.info(f'设置 Sovits 模型成功: {await response.text()}')
        except Exception:
            raise

    async def _send_text_to_api(self, text: str):
        '''发送文本到 API，将文本添加到负载中，调用 API，接收返回的音频块并将音频块放入音频队列'''

        self._params['text'] = text
        try:
            async with self._session.post(f'{self._base_url}/tts', json=self._params) as response:
                if response.status == 200:
                    async for chunk in response.content.iter_any():  # 逐块读取 HTTP 响应的内容
                        if chunk:
                            await self._audio_chunk_queue.put(chunk)
                else:
                    logger.error(f'GPT_SoVITS 的 TTS API 请求失败！\n{response.status} : {await response.text()}')
            await self._audio_chunk_queue.put(self._AUDIO_SENTINEL)
        except Exception:
            raise

    async def _stream_tts_worker(self):
        '''流式 TTS 工作器'''

        self._text_buffer = ''
        while self._is_running:
            try:
                text_chunk = await wait_for(self._text_queue.get(), self._timeout_sec)
                if text_chunk is self._TEXT_FINAL_SENTINEL:
                    await self._send_text_to_api(self._text_buffer)
                    self._text_buffer = ''
                    self._text_queue.task_done()
                    continue
                self._text_buffer += text_chunk
                text_buffer_part = split(self._PUNCTUATION, self._text_buffer)
                if len(text_buffer_part) > 1:
                    for i in range(0, len(text_buffer_part) - 1, 2):
                        text = text_buffer_part[i] + self._text_buffer[i + 1]
                        await self._send_text_to_api(text)
                    self._text_buffer = text_buffer_part[-1]
                self._text_queue.task_done()
            except TimeoutError:
                if self._text_buffer.strip():
                    await self._send_text_to_api(self._text_buffer)
                self._text_buffer = ''
            except CancelledError:
                break
            except Exception:
                raise

    async def _audio_data_write_in_audio_output_stream(self, audio_data: np.ndarray):
        '''音频数据写入音频输出流'''

        if self._audio_output_stream and audio_data.size > 0:
            try:
                await to_thread(self._audio_output_stream.write, audio_data)
            except Exception:
                raise

    async def _audio_play_worker(self):
        '''音频播放工作器'''

        while self._is_running:
            try:
                chunk = await self._audio_chunk_queue.get()
                if chunk is self._AUDIO_SENTINEL:
                    if self._is_skip_wav_header and len(self._audio_buffer) > 0:
                        audio_data = np.frombuffer(self._audio_buffer, dtype=np.int16)
                        await self._audio_data_write_in_audio_output_stream(audio_data)
                        self._audio_buffer = b''
                    self._audio_chunk_queue.task_done()
                    continue

                self._audio_buffer += chunk

                # 跳过 WAV 文件头部
                if not self._is_skip_wav_header and len(self._audio_buffer) >= 44:
                    self._audio_buffer = self._audio_buffer[44:]
                    self._is_skip_wav_header = True

                if self._is_skip_wav_header:  # 音频数据是 16 位整型，需要按 2 字节倍数处理
                    while len(self._audio_buffer) >= self._buffer_size:
                        audio_data_to_play = self._audio_buffer[: self._buffer_size]
                        self._audio_buffer = self._audio_buffer[self._buffer_size :]
                        audio_data = np.frombuffer(audio_data_to_play, dtype=np.int16)  # 从字节缓冲区创建 NumPy 数组
                        await self._audio_data_write_in_audio_output_stream(audio_data)
                self._audio_chunk_queue.task_done()
            except CancelledError:
                break
            except Exception:
                raise

    # 功能相关
    async def put_text_in_queue(self, text: str):
        '''放入文本到队列，清洗文本并放入文本队列'''

        if not self._is_running or not isinstance(text, str) or not text:
            return

        try:
            sanitized_text = self._PATTERN.sub(r'', text)  # 清洗表情和符号
            sanitized_text = sub(r'([*_`~])', '', sanitized_text)  # 清洗 Markdown 标记
            sanitized_text = sanitized_text.strip()  # 清洗前后空白
            if sanitized_text:
                await self._text_queue.put(text)
        except Exception:
            raise

    async def emit_text_final_signal(self):
        '''发送文本结束信号'''

        if self._is_running:
            await self._text_queue.put(self._TEXT_FINAL_SENTINEL)

    async def stop(self):
        '''停止 GPT_SoVITS 代理，关闭任务并清理资源'''

        if not self._is_running:
            return
        logger.info('<stop> GPT_SoVITS 正在停止中···')
        self._is_running = False

        if self._text_queue:
            await self._text_queue.put(self._TEXT_FINAL_SENTINEL)

        for task in self._tasks:
            if not task.done():
                task.cancel()  # 取消正在运行的协程任务
        await asyncio.gather(*self.tasks, return_exceptions=True)  # 并发运行多个异步任务
        self._tasks.clear()

        if self._audio_output_stream:
            try:
                if self._audio_output_stream.active:
                    self._audio_output_stream.stop()
                self._audio_output_stream.close()
            except Exception:
                raise
            finally:
                self._audio_output_stream = None

        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

        self._audio_buffer = b''
        self._is_skip_wav_header = False

        logger.info('<stop> 停止 GPT_SoVITS 代理完成')
