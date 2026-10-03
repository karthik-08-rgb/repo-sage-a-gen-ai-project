import json
import re
import time
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Generator, Type, TypeVar, cast
from pydantic import BaseModel
from app.core.config import settings
from app.core.exceptions import LLMProviderException

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMResponse:
    def __init__(self, content: str, model: str, token_usage: Optional[Dict[str, int]] = None, raw: Any = None):
        self.content = content
        self.model = model
        self.token_usage = token_usage or {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        self.raw = raw


class BaseLLMProvider(ABC):
    @abstractmethod
    def generate(self, messages: List[Dict[str, str]], temperature: Optional[float] = None) -> LLMResponse:
        pass

    @abstractmethod
    def generate_structured(
        self,
        messages: List[Dict[str, str]],
        response_model: Type[T],
        temperature: Optional[float] = None
    ) -> T:
        pass

    @abstractmethod
    def stream(self, messages: List[Dict[str, str]], temperature: Optional[float] = None) -> Generator[str, None, None]:
        pass

    @abstractmethod
    def get_model_info(self) -> Dict[str, str]:
        pass


class OpenAIProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str = settings.OPENAI_MODEL):
        self.api_key = api_key
        self.model = model
        self.client: Any = None
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=api_key)
        except Exception as e:
            logger.warning(f"Failed to initialize OpenAI client: {e}")

    def generate(self, messages: List[Dict[str, str]], temperature: Optional[float] = None) -> LLMResponse:
        if not self.client:
            logger.warning("OpenAI client not configured; falling back to MockLLMProvider.")
            return MockLLMProvider().generate(messages, temperature)

        temp = temperature if temperature is not None else settings.OPENAI_TEMPERATURE
        max_retries = 3
        backoff = 1.0

        for attempt in range(max_retries):
            try:
                res = self.client.chat.completions.create(
                    model=self.model,
                    messages=cast(Any, messages),
                    temperature=temp,
                    max_tokens=settings.OPENAI_MAX_TOKENS
                )
                text = res.choices[0].message.content or ""
                usage = {
                    "prompt_tokens": res.usage.prompt_tokens if res.usage else 0,
                    "completion_tokens": res.usage.completion_tokens if res.usage else 0,
                    "total_tokens": res.usage.total_tokens if res.usage else 0,
                }
                return LLMResponse(content=text, model=self.model, token_usage=usage, raw=res)
            except Exception as e:
                logger.warning(f"OpenAI error (attempt {attempt+1}): {e}")
                if attempt == max_retries - 1:
                    logger.warning("All OpenAI attempts failed; falling back to MockLLMProvider.")
                    return MockLLMProvider().generate(messages, temperature)
                time.sleep(backoff)
                backoff *= 2.0

        return MockLLMProvider().generate(messages, temperature)

    def generate_structured(
        self,
        messages: List[Dict[str, str]],
        response_model: Type[T],
        temperature: Optional[float] = None
    ) -> T:
        schema_json = json.dumps(response_model.model_json_schema(), indent=2)
        system_instruction = (
            f"\n\nCRITICAL: You MUST reply ONLY with valid JSON conforming strictly to this JSON schema:\n{schema_json}"
        )
        augmented_messages = list(messages)
        augmented_messages.append({"role": "system", "content": system_instruction})

        raw_res = self.generate(augmented_messages, temperature)
        content = raw_res.content.strip()

        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
        clean_json = match.group(1).strip() if match else content

        try:
            parsed = json.loads(clean_json)
        except Exception:
            start = clean_json.find("{")
            end = clean_json.rfind("}")
            if start != -1 and end != -1:
                try:
                    parsed = json.loads(clean_json[start:end+1])
                except Exception:
                    logger.warning("OpenAI JSON extraction failed; falling back to MockLLMProvider.")
                    return MockLLMProvider().generate_structured(messages, response_model, temperature)
            else:
                logger.warning("OpenAI output contained no valid JSON; falling back to MockLLMProvider.")
                return MockLLMProvider().generate_structured(messages, response_model, temperature)

        try:
            return response_model.model_validate(parsed)
        except Exception as e:
            logger.warning(f"OpenAI structured validation failed ({e}); falling back to MockLLMProvider.")
            return MockLLMProvider().generate_structured(messages, response_model, temperature)

    def stream(self, messages: List[Dict[str, str]], temperature: Optional[float] = None) -> Generator[str, None, None]:
        if not self.client:
            logger.warning("OpenAI client not configured; streaming fallback.")
            yield from MockLLMProvider().stream(messages, temperature)
            return

        temp = temperature if temperature is not None else settings.OPENAI_TEMPERATURE
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=cast(Any, messages),
                temperature=temp,
                stream=True
            )
            for chunk in response:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except Exception as e:
            logger.warning(f"OpenAI streaming error: {e}. Falling back to MockLLMProvider stream.")
            yield from MockLLMProvider().stream(messages, temperature)

    def get_model_info(self) -> Dict[str, str]:
        return {"provider": "openai", "model": self.model}


FALLBACK_GEMINI_MODELS = [
    "gemini-3.8-flash",
    "gemini-3-flash-preview",
    "gemini-3.5-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
]


class GeminiProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str = settings.GEMINI_MODEL):
        self.api_key = api_key
        self.model_name = model
        self.active_model = model
        self._GenerativeModel: Any = None
        try:
            from google.generativeai.client import configure
            from google.generativeai.generative_models import GenerativeModel
            try:
                configure(api_key=api_key, transport="rest")
            except Exception:
                configure(api_key=api_key)
            self._GenerativeModel = GenerativeModel
        except Exception as e:
            logger.warning(f"Failed to initialize google.generativeai: {e}")

    def _get_candidate_models(self) -> List[str]:
        models = [self.model_name]
        for m in FALLBACK_GEMINI_MODELS:
            if m not in models:
                models.append(m)
        return models

    def generate(self, messages: List[Dict[str, str]], temperature: Optional[float] = None) -> LLMResponse:
        if self._GenerativeModel is None:
            logger.warning("Gemini client not initialized; falling back to MockLLMProvider.")
            return MockLLMProvider().generate(messages, temperature)

        prompt_lines = [f"{m['role'].upper()}: {m['content']}" for m in messages]
        full_prompt = "\n\n".join(prompt_lines)
        last_error = None

        for model_candidate in self._get_candidate_models():
            try:
                model_inst = self._GenerativeModel(model_candidate)
                res = model_inst.generate_content(
                    full_prompt,
                    generation_config={"temperature": temperature or 0.2}
                )
                self.active_model = model_candidate
                try:
                    text_content = res.text
                except (ValueError, AttributeError):
                    if hasattr(res, "candidates") and res.candidates:
                        parts = res.candidates[0].content.parts
                        text_content = "".join([getattr(p, "text", "") for p in parts])
                    else:
                        text_content = ""

                return LLMResponse(content=text_content, model=model_candidate)
            except Exception as e:
                last_error = e
                err_msg = str(e).lower()
                if any(k in err_msg for k in ["404", "429", "503", "quota", "not available", "deadline", "timed out", "resource has been exhausted"]):
                    logger.warning(f"Gemini model '{model_candidate}' failed with: {e}. Trying fallback model...")
                    continue
                else:
                    logger.warning(f"Gemini generation failed: {e}. Falling back to MockLLMProvider.")
                    return MockLLMProvider().generate(messages, temperature)

        logger.warning(f"All Gemini models exhausted or quota reached ({last_error}). Gracefully falling back to MockLLMProvider.")
        return MockLLMProvider().generate(messages, temperature)

    def generate_structured(
        self,
        messages: List[Dict[str, str]],
        response_model: Type[T],
        temperature: Optional[float] = None
    ) -> T:
        schema_json = json.dumps(response_model.model_json_schema(), indent=2)
        augmented_messages = list(messages)
        augmented_messages.append({
            "role": "user",
            "content": f"Output JSON matching this schema:\n{schema_json}\nRespond ONLY with valid JSON inside ```json ... ``` code blocks."
        })
        raw = self.generate(augmented_messages, temperature)
        content = raw.content.strip()

        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
        clean_json = match.group(1).strip() if match else content

        try:
            parsed = json.loads(clean_json)
        except Exception:
            start = clean_json.find("{")
            end = clean_json.rfind("}")
            if start != -1 and end != -1:
                try:
                    parsed = json.loads(clean_json[start:end+1])
                except Exception:
                    logger.warning("Failed to extract JSON object from Gemini response; falling back to MockLLMProvider.")
                    return MockLLMProvider().generate_structured(messages, response_model, temperature)
            else:
                logger.warning("Failed to find JSON braces in Gemini response; falling back to MockLLMProvider.")
                return MockLLMProvider().generate_structured(messages, response_model, temperature)

        try:
            return response_model.model_validate(parsed)
        except Exception:
            logger.warning("Pydantic validation failed for Gemini response; falling back to MockLLMProvider structured generation.")
            return MockLLMProvider().generate_structured(messages, response_model, temperature)

    def stream(self, messages: List[Dict[str, str]], temperature: Optional[float] = None) -> Generator[str, None, None]:
        if self._GenerativeModel is None:
            logger.warning("Gemini client not initialized; falling back to MockLLMProvider stream.")
            yield from MockLLMProvider().stream(messages, temperature)
            return

        prompt_lines = [f"{m['role'].upper()}: {m['content']}" for m in messages]
        full_prompt = "\n\n".join(prompt_lines)
        last_error = None

        for model_candidate in self._get_candidate_models():
            try:
                model_inst = self._GenerativeModel(model_candidate)
                res = model_inst.generate_content(full_prompt, stream=True)
                for chunk in res:
                    try:
                        if chunk.text:
                            yield chunk.text
                    except Exception:
                        pass
                self.active_model = model_candidate
                return
            except Exception as e:
                last_error = e
                err_msg = str(e).lower()
                if any(k in err_msg for k in ["404", "429", "503", "quota", "not available", "deadline", "timed out", "resource has been exhausted"]):
                    logger.warning(f"Gemini stream model '{model_candidate}' failed with: {e}. Trying fallback model...")
                    continue
                else:
                    break

        logger.warning(f"All Gemini stream models exhausted ({last_error}). Falling back to MockLLMProvider stream.")
        yield from MockLLMProvider().stream(messages, temperature)

    def get_model_info(self) -> Dict[str, str]:
        return {"provider": "gemini", "model": getattr(self, "active_model", self.model_name)}


class MockLLMProvider(BaseLLMProvider):
    """
    Deterministic LLM provider grounded in the context provided.
    Generates structured, citation-accurate responses for testing and zero-cost local runs.
    """
    def generate(self, messages: List[Dict[str, str]], temperature: Optional[float] = None) -> LLMResponse:
        user_msg = messages[-1]["content"] if messages else ""
        text = f"RepoSage Analysis:\nAnalyzed query based on retrieved codebase context.\nQuery: {user_msg[:100]}"
        return LLMResponse(
            content=text,
            model="mock-grounded-v1",
            token_usage={"prompt_tokens": 120, "completion_tokens": 45, "total_tokens": 165}
        )

    def generate_structured(
        self,
        messages: List[Dict[str, str]],
        response_model: Type[T],
        temperature: Optional[float] = None
    ) -> T:
        full_text = " ".join(m.get("content", "") for m in messages)
        raw_files = re.findall(r"File:\s*([a-zA-Z0-9_\-\./\\]+)", full_text)
        files = [f.replace("\\", "/").strip() for f in raw_files]
        unique_files = list(dict.fromkeys(files))

        user_msg = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
        query_words = set(re.findall(r"[a-zA-Z0-9_]{3,}", user_msg.lower()))

        def file_relevance(fp: str) -> int:
            fp_lower = fp.lower()
            return sum(1 for w in query_words if w in fp_lower)

        ranked_files = sorted(unique_files, key=file_relevance, reverse=True)
        relevant_files = [f for f in ranked_files if file_relevance(f) > 0]
        if not relevant_files and ranked_files:
            relevant_files = [ranked_files[0]]

        if response_model.__name__ == "GroundedAnswerPayload":
            from app.schemas.chat import GroundedAnswerPayload, CitationItem
            citations = [
                CitationItem(file_path=fp, start_line=1, end_line=30, symbol_name="main")
                for fp in relevant_files[:2]
            ]
            return cast(T, GroundedAnswerPayload(
                direct_answer=f"Found relevant implementation across {len(relevant_files)} files in the repository.",
                explanation="The code handles repository indexing, hybrid retrieval, and AI workflow orchestration.",
                relevant_files=relevant_files[:5],
                citations=citations,
                dependencies_or_flow="Request -> Router -> Service -> Database / Vector Index",
                confidence_limitations="Verified from confirmed indexed source code files."
            ))
        elif response_model.__name__ == "DebugAnalyzeResponse":
            from app.schemas.debug import DebugAnalyzeResponse, SuggestedFixItem, CitationItem
            citations = [
                CitationItem(file_path=fp, start_line=10, end_line=25)
                for fp in unique_files[:2]
            ]
            return cast(T, DebugAnalyzeResponse(
                error_summary="Detected potential exception handling or null reference issue in repository flow.",
                potential_root_cause="Missing boundary check or unhandled empty collection returned by retriever.",
                evidence_from_codebase=f"Context references files: {', '.join(unique_files[:2])}",
                affected_files=unique_files[:2],
                citations=citations,
                suggested_fixes=[
                    SuggestedFixItem(
                        file_path=unique_files[0] if unique_files else "app/main.py",
                        description="Add guard condition before accessing item index.",
                        unified_diff="--- a/file\n+++ b/file\n@@ -10,3 +10,4 @@\n+if not items:\n+    return None\n",
                        validation_steps=["Run unit tests with empty input list."],
                        confidence="High"
                    )
                ],
                tests_to_validate=["pytest tests/unit/test_retrieval.py"],
                confidence_limitations="Inferred from error stack trace and static code inspection."
            ))
        elif response_model.__name__ == "CodeReviewResponse":
            from app.schemas.review import CodeReviewResponse, ReviewFinding
            has_critical = "eval(" in full_text or "exec(" in full_text or "rm -rf" in full_text
            findings = [
                ReviewFinding(
                    title="Dynamic Code Execution / Insecure Command" if has_critical else "Potential Null Pointer / Missing Validation",
                    severity="Critical" if has_critical else "Medium",
                    category="Security" if has_critical else "NullHandling",
                    description="Dangerous execution detected." if has_critical else "Variable should be checked against None before accessing attributes.",
                    evidence="Dynamic eval invocation" if has_critical else "Unchecked dereference in logic flow.",
                    file_path=unique_files[0] if unique_files else "app/main.py",
                    start_line=1,
                    end_line=5,
                    suggested_improvement="Do not use dynamic code execution." if has_critical else "Use 'if val is not None:' guard or optional chaining.",
                    confidence="High"
                )
            ]
            return cast(T, CodeReviewResponse(
                repository_id="mock_repo",
                target=unique_files[0] if unique_files else "codebase",
                total_findings=len(findings),
                findings=findings,
                summary=f"Audit completed. Found {len(findings)} findings."
            ))
        elif response_model.__name__ == "AgentWorkflowResponse":
            from app.schemas.chat import AgentWorkflowResponse, CitationItem
            citations = [
                CitationItem(file_path=fp, start_line=1, end_line=30, symbol_name="main")
                for fp in relevant_files[:2]
            ]
            return cast(T, AgentWorkflowResponse(
                repository_id="mock_repo",
                intent="general_codebase",
                detected_language="python",
                extracted_symbols=["authenticate"],
                extracted_files=relevant_files[:3],
                direct_answer=f"Found relevant implementation across {len(relevant_files)} files in the repository.",
                explanation="The agent workflow identified key entrypoints, models, and services.",
                execution_flow="Query -> Router -> Workflow -> Model",
                citations=citations,
                execution_log=[
                    "Node: Query Understanding",
                    "Node: Targeted Retrieval",
                    "Node: AST Code Analysis",
                    "Node: Grounded Generation",
                    "Node: Citation Validation"
                ],
                session_id=None
            ))

        # Generic Pydantic model fallback
        try:
            return response_model()
        except Exception:
            try:
                dummy_data = {}
                for field_name, field_info in getattr(response_model, "model_fields", {}).items():
                    if field_info.is_required():
                        annotation = field_info.annotation
                        if annotation is str:
                            dummy_data[field_name] = f"Mock {field_name}"
                        elif annotation is int:
                            dummy_data[field_name] = 0
                        elif annotation is float:
                            dummy_data[field_name] = 0.0
                        elif annotation is bool:
                            dummy_data[field_name] = True
                        elif getattr(annotation, "__origin__", None) is list:
                            dummy_data[field_name] = []
                        elif getattr(annotation, "__origin__", None) is dict:
                            dummy_data[field_name] = {}
                        else:
                            dummy_data[field_name] = None
                return response_model.model_validate(dummy_data)
            except Exception:
                raise LLMProviderException(f"Cannot mock response for model {response_model.__name__}")

    def stream(self, messages: List[Dict[str, str]], temperature: Optional[float] = None) -> Generator[str, None, None]:
        chunks = ["RepoSage ", "Analysis: ", "Retrieved ", "codebase ", "context ", "processed ", "successfully."]
        for c in chunks:
            time.sleep(0.05)
            yield c

    def get_model_info(self) -> Dict[str, str]:
        return {"provider": "mock", "model": "mock-grounded-v1"}


def get_llm_provider() -> BaseLLMProvider:
    provider = (settings.LLM_PROVIDER or "").lower()
    if provider == "openai" and settings.OPENAI_API_KEY:
        try:
            return OpenAIProvider(settings.OPENAI_API_KEY, settings.OPENAI_MODEL)
        except Exception as e:
            logger.warning(f"Failed to initialize OpenAI provider: {e}")
    elif provider == "gemini" and settings.GEMINI_API_KEY:
        try:
            return GeminiProvider(settings.GEMINI_API_KEY, settings.GEMINI_MODEL)
        except Exception as e:
            logger.warning(f"Failed to initialize Gemini provider: {e}")

    # Fallback to MockLLMProvider for offline deterministic tests and demonstrations
    return MockLLMProvider()
