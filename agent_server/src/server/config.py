from os import path
from pathlib import Path
from textwrap import dedent

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).parent.parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=path.join(ROOT_DIR, '.env'), env_file_encoding='utf-8', case_sensitive=True
    )

    # Postgres 相关
    POSTGRES_CONNECTION_STRING: str

    # GPT_SoVITS 相关
    GPT_WEIGHTS_PATH: str
    SOVITS_WEIGHTS_PATH: str
    REF_AUDIO_PATH: str


settings = Settings()


class Config:
    '''配置'''

    def __init__(self):
        self._related_to_graph_state()
        self._related_to_llm()
        self._related_to_gpt_sovits()

    def _related_to_graph_state(self):
        '''图状态相关'''

        self.system_prompt = dedent(
            '''\
            你是一位强大的助手，能通过将复杂问题拆解为更小的步骤来解决它们。
            你的首要目标是尽可能准确，完整地回答用户的问题。为实现这一目标，你可以使用提供给你的各种信息和工具。

            以下是你的思考要点：
                1. 分析用户请求
                    仔细理解用户的问题，判断是否需要外部信息或帮助才能作答。
                2. 规划步骤
                    若问题复杂，逐步思考，决定首先使用哪个工具。若一个工具的输出需作为下一个工具的输入，则规划好顺序。
                3. 必要时使用工具
                    不要猜测。若不知道某事或需要外部信息，请使用工具。
                4. 观察并重新规划
                    使用工具后，分析结果，判断信息是否足够。若不足，规划下一步，可能需使用另一工具或同一工具但更换输入。
                5. 最终答案
                    一旦确信已掌握所有必要信息，向用户提供最终，全面的答案。此阶段不得输出工具调用。

                你必须直接回答用户，若已得出答案。否则，必须输出一个或多个工具调用以收集信息。

            你于过去某一时刻被创建，内部知识完全冻结于过去，对之后发生的任何事情一无所知。
            因此，严禁依赖记忆回答涉及“当前”，“今天”，“现在”或需实时确定的任何问题。
            若问题与时间相关，必须使用相关工具获取当前日期和时间，并据此作答或进一步搜索。
            '''
        )
        self.episode_memeory_prompt = f'''\
        下面提供相关的情景记忆，情景记忆是在过去的对话中提取并保存的对话数据，记录了优秀的对话情节。
        便于你在接下来的对话中参考，学习和使用。
        每段情景记忆都包括四个部分：
            1. 对话的情景与背景，即当时对话的情况，发生了什么，进行了怎样的对话？
            2. 智能体（你）在情景中的内部推理过程与观察，得出正确行动并获得结果的思考。
            3. 智能体（你）在情景中具体做了什么？如何做的？以何种形式完成的？包括任何对行动成功至关重要的信息和细节。
            4. 结果与复盘，哪些方面做得好？下次在哪些方面可以做得更好或者改进？
        '''
        self.user_name = '理灵'
        self.ai_name = '洛璃'
        self.chat_language = '中文'

        self.state = {
            'system_prompt': self.system_prompt,
            'user_name': self.user_name,
            'ai_name': self.ai_name,
            'chat_language': self.chat_language,
        }

    def _related_to_llm(self):
        '''LLM 相关'''

        # Ollama 相关
        self.ollama_llm = None
        self.ollama_base_url = None
        self.ollama_temperature = None
        self.ollama_num_predict = None

        # DeepSeek 相关
        self.deepseek_llm = None
        self.deepseek_api_key = None
        self.deepseek_temperature = None
        self.deepseek_max_tokens = None

    def _related_to_gpt_sovits(self):
        '''GPT_SoVITS 相关'''

        self.host = '127.0.0.1'
        self.port = '9880'
        self.gpt_sovits_tts_config_path = r'GPT_SoVITS/configs/tts_infer.yaml'
        self.gpt_weights_path = settings.GPT_WEIGHTS_PATH
        self.sovits_weights_path = settings.SOVITS_WEIGHTS_PATH
        self.ref_audio_path = settings.REF_AUDIO_PATH
        self.prompt_text = '奥，我明白，你们外乡人难免有些庸俗的认知，但别忘了，神明也分平庸与优秀'
        self.text_split_method = 'cut3'
        self.speed_factor = 1.0
        self.sample_steps = 16
