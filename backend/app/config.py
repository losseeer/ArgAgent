"""§9.3 `.env.example` 的唯一读取端（pydantic-settings）。

硬约束：所有 key 都可空——空 key 必须仍能走完一轮对话（§6.5 降级到兜底模板）。
端口与模型名默认值即 §5.2 版本基线，不在别处重复写死。
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # 主 LLM（推荐填；不填则走本地 Ollama）
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/anthropic"
    deepseek_model: str = "deepseek-flash"

    # 本地回退 LLM（不填则降级兜底模板）
    ollama_model: str = "qwen2.5:14b-instruct-q5_K_M"
    ollama_host: str = "http://host.docker.internal:11434"

    # Web 检索（不填则降级 DuckDuckGo）
    tavily_api_key: str = ""

    # 内容审核二次判（不填则只走本地模式表并显式标"审核降级"，§6.13 / N8）
    moderation_api_key: str = ""

    # 端口
    backend_port: int = 8010
    frontend_port: int = 3005
    chroma_port: int = 8011

    @property
    def primary_configured(self) -> bool:
        return bool(self.deepseek_api_key)

    @property
    def moderation_mode(self) -> str:
        """SSE `safety.status{mode}` 与 BadgeBar 角标的唯一数据源（§6.13）。"""
        return "heuristic+remote" if self.moderation_api_key else "heuristic_only"


@lru_cache
def get_settings() -> Settings:
    return Settings()
