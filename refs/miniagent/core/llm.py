"""统一的LLM接口，支持不同的LLM调用（如OpenAI、Azure、Anthropic等）和基础计量。
实现输入输出的规范化，方便上层组件调用和替换底层LLM实现。
"""


import os
import json
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Iterator, Callable
from dataclasses import dataclass
from types import SimpleNamespace

# 引入 OpenAI 的官方类型作为整个系统的标准规范
from openai import OpenAI
from openai.types.chat import ChatCompletion, ChatCompletionChunk
from anthropic import Anthropic


class LLMException(Exception):
    """LLM 调用过程中发生的异常
    1. 不支持的 provider_type
    2. 缺失 API key
    3. 其他调用错误（如网络问题、API 错误等）
    """
    def unsupported_provider(self, provider_type: str) -> Exception:
        return Exception(f"Unsupported LLM provider: {provider_type}")
    
    def missing_api_key(self) -> Exception:
        return Exception("API key is required for the selected LLM provider.")
    
    def api_call_failed(self, error: Exception) -> Exception:
        return Exception(f"LLM API call failed: {str(error)}")


class BaseProviderHandler(ABC):
    """
    大模型提供商的抽象处理器。
    所有的子类必须将自身平台的响应转换为统一的 OpenAI 规范返回。
    """
    @abstractmethod
    def generate(self, model: str, messages: List[Dict], tools: Optional[List[Dict]] = None, **kwargs) -> ChatCompletion:
        pass

    @abstractmethod
    def stream_generate(self, model: str, messages: List[Dict], tools: Optional[List[Dict]] = None, **kwargs) -> Iterator[ChatCompletionChunk]:
        pass

    @abstractmethod
    def count_tokens(self, messages: List[Dict]) -> int:
        pass


class OpenAIHandler(BaseProviderHandler):
    """OpenAI 原生处理器"""
    
    def __init__(self, api_key: Optional[str], base_url: Optional[str] = None, **kwargs):
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def generate(self, model: str, messages: List[Dict], tools: Optional[List[Dict]] = None, **kwargs) -> ChatCompletion:
        req_kwargs = {"model": model, "messages": messages, "stream": False, **kwargs}
        if tools:
            req_kwargs["tools"] = tools
        return self.client.chat.completions.create(**req_kwargs)

    def stream_generate(self, model: str, messages: List[Dict], tools: Optional[List[Dict]] = None, **kwargs) -> Iterator[ChatCompletionChunk]:
        req_kwargs = {"model": model, "messages": messages, "stream": True, **kwargs}
        if tools:
            req_kwargs["tools"] = tools
        yield from self.client.chat.completions.create(**req_kwargs)

    def count_tokens(self, messages: List[Dict]) -> int:
        # 简单估算或接入 tiktoken
        return len(json.dumps(messages)) // 4


class AnthropicHandler(BaseProviderHandler):
    """Anthropic 处理器 (当前预留转换接口)"""
    
    def __init__(self, api_key: Optional[str], **kwargs):
        self.api_key = api_key
        # 未来这里可以: from anthropic import Anthropic; self.client = Anthropic(api_key=api_key)

    def generate(self, model: str, messages: List[Dict], tools: Optional[List[Dict]] = None, **kwargs) -> ChatCompletion:
        raise NotImplementedError(
            "Anthropic 暂未适配。\n"
            "实现路径: 1. 转换 messages/tools -> 2. 调用 Anthropic API -> 3. 封装为 ChatCompletion 返回"
        )

    def stream_generate(self, model: str, messages: List[Dict], tools: Optional[List[Dict]] = None, **kwargs) -> Iterator[ChatCompletionChunk]:
        raise NotImplementedError("Anthropic 流式调用暂未适配。")

    def count_tokens(self, messages: List[Dict]) -> int:
        raise NotImplementedError("Anthropic token 计算暂未适配。")
    
    # TODO: 未来实现 AnthropicHandler 时，需要完成以下步骤：
    # [预留] 将 OpenAI 格式的入参转换为 Anthropic 格式
    # [预留] 将 Anthropic 非流式 Message 响应封装为 OpenAI ChatCompletion 对象。
    # [预留] 将 Anthropic 的流式事件块转换为 OpenAI 的 ChatCompletionChunk 格式。


class BaseLLM:
    # 注册表：将 provider_type 映射到具体的 Handler 类
    _HANDLERS = {
        "openai": OpenAIHandler,
        "anthropic": AnthropicHandler,
        # 未来可以轻松扩展: "azure": AzureHandler
    }

    def __init__(
        self, 
        provider_type: str = "openai", 
        model: str = "gpt-4o", 
        api_key: Optional[str] = None, 
        **kwargs
    ):
        self.provider_type = provider_type.lower()
        self.model = model
        
        # 提取 LLM 的基础生成参数 (如温度、最大 token 数)，其余的作为 handler 的初始化参数
        self.generation_params = {
            "temperature": kwargs.pop("temperature", 0.7),
            "max_tokens": kwargs.pop("max_tokens", None)
        }
        # 移除空值参数
        self.generation_params = {k: v for k, v in self.generation_params.items() if v is not None}

        # 根据配置分发并初始化 Handler
        handler_class = self._HANDLERS.get(self.provider_type)
        if not handler_class:
            raise ValueError(
                f"不支持的 provider_type: '{self.provider_type}'。 "
                f"当前支持: {list(self._HANDLERS.keys())}"
            )
        
        # 初始化处理器
        self.handler: BaseProviderHandler = handler_class(api_key=api_key, **kwargs)

    def generate(self, messages: List[Dict], tools: Optional[List[Dict]] = None) -> ChatCompletion:
        """非流式调用委派"""
        return self.handler.generate(
            model=self.model, 
            messages=messages, 
            tools=tools, 
            **self.generation_params
        )

    def stream_generate(self, messages: List[Dict], tools: Optional[List[Dict]] = None) -> Iterator[ChatCompletionChunk]:
        """流式调用委派"""
        return self.handler.stream_generate(
            model=self.model, 
            messages=messages, 
            tools=tools, 
            **self.generation_params
        )

    def count_tokens(self, messages: List[Dict]) -> int:
        """Token 计数委派"""
        return self.handler.count_tokens(messages)
    

