import json
import time
from typing import Optional, Any, List, Dict
from anthropic import Anthropic
from tenacity import retry, stop_after_attempt, wait_exponential
from loguru import logger

from ..config import get_config


class ClaudeClient:
    def __init__(self, api_key: Optional[str] = None):
        config = get_config()
        self.api_key = api_key or config.ANTHROPIC_API_KEY
        if not self.api_key:
            logger.warning("No Anthropic API key provided. LLM features will be limited.")
        self.client = Anthropic(api_key=self.api_key) if self.api_key else None
        self.max_tokens = config.MAX_TOKENS
        self.temperature = config.TEMPERATURE
        self.model = "claude-opus-4-520251120"
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    def complete(
        self,
        system_prompt: str,
        user_message: str,
        tools_schema: Optional[List[Dict]] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        json_output: bool = False
    ) -> Dict[str, Any]:
        if not self.client:
            logger.error("Claude client not initialized. API key missing.")
            return {"error": "API key not configured", "text": ""}
        
        messages = [{"role": "user", "content": user_message}]
        
        extra_kwargs = {}
        if json_output:
            extra_kwargs["response_format"] = {"type": "json_object"}
        
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens or self.max_tokens,
                temperature=temperature if temperature is not None else self.temperature,
                system=system_prompt,
                messages=messages,
                tools=tools_schema,
                **extra_kwargs
            )
            
            result = {
                "text": response.content[0].text if response.content else "",
                "usage": {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens
                },
                "stop_reason": response.stop_reason
            }
            
            if tools_schema and hasattr(response.content[0], 'type') and response.content[0].type == 'tool_use':
                result["tool_use"] = response.content[0].input
            
            return result
            
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            return {"error": str(e), "text": ""}
    
    def complete_streaming(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ):
        if not self.client:
            logger.error("Claude client not initialized. API key missing.")
            return
        
        messages = [{"role": "user", "content": user_message}]
        
        try:
            with self.client.messages.stream(
                model=self.model,
                max_tokens=max_tokens or self.max_tokens,
                temperature=temperature if temperature is not None else self.temperature,
                system=system_prompt,
                messages=messages
            ) as stream:
                for text in stream.text_stream:
                    yield text
        except Exception as e:
            logger.error(f"Claude streaming error: {e}")
            yield f"Error: {e}"
    
    def parse_json_response(self, response: Dict[str, Any]) -> Optional[Dict]:
        try:
            text = response.get("text", "")
            if not text:
                return None
            
            start = text.find('{')
            end = text.rfind('}') + 1
            if start != -1 and end > start:
                json_str = text[start:end]
                return json.loads(json_str)
            
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON response: {e}")
            return None
    
    def truncate_text(self, text: str, max_chars: int) -> str:
        if len(text) <= max_chars:
            return text
        return text[:max_chars] + "... [truncated]"
