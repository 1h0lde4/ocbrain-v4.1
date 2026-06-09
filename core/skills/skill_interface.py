"""
OCBrain v4.1.1 — SkillInterface
Versioned, typed, cacheable, MCP-ready skill base class.
"""
import asyncio, hashlib, json, logging, time, uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("ocbrain.skills")

class SkillCategory(str, Enum):
    REASONING="reasoning"; MEMORY="memory"; PLANNING="planning"
    EXECUTION="execution"; PERCEPTION="perception"; COMMUNICATION="communication"
    LEARNING="learning"; GOVERNANCE="governance"; UTILITY="utility"

class SkillError(Exception): pass
class SkillExecutionError(SkillError): pass
class SkillTimeoutError(SkillError): pass
class SkillValidationError(SkillError): pass

@dataclass
class SkillExecutionConfig:
    mode: str = "inline"
    timeout_sec: float = 30.0
    memory_limit_mb: int = 512
    allowed_imports: List[str] = field(default_factory=list)

@dataclass
class SkillInput:
    name: str; type: str; description: str
    required: bool = True; default: Any = None
    enum: Optional[List[str]] = None
    min_value: Optional[float] = None; max_value: Optional[float] = None

    def validate(self, value: Any) -> Tuple[bool, Optional[str]]:
        if value is None:
            return (False, f"Required '{self.name}'") if self.required else (True, None)
        type_map = {"string":str,"number":(int,float),"integer":int,"boolean":bool,"object":dict,"array":list}
        expected = type_map.get(self.type)
        if expected and not isinstance(value, expected):
            return False, f"'{self.name}': expected {self.type}, got {type(value).__name__}"
        if self.enum and value not in self.enum:
            return False, f"'{self.name}': {value} not in {self.enum}"
        if self.type in ("number","integer"):
            if self.min_value is not None and value < self.min_value:
                return False, f"'{self.name}': {value} < min {self.min_value}"
            if self.max_value is not None and value > self.max_value:
                return False, f"'{self.name}': {value} > max {self.max_value}"
        return True, None

@dataclass
class SkillOutput:
    type: str; description: str
    schema: Optional[Dict] = None

@dataclass
class SkillMetadata:
    name: str; version: str; description: str
    category: SkillCategory; author: str
    inputs: List[SkillInput] = field(default_factory=list)
    outputs: SkillOutput = field(default_factory=lambda: SkillOutput("object",""))
    dependencies: Optional[List[str]] = None; tags: Optional[List[str]] = None
    timeout: float = 30.0; max_retries: int = 3
    cacheable: bool = False; cache_ttl: Optional[float] = None
    requires_llm: bool = False
    execution: SkillExecutionConfig = field(default_factory=SkillExecutionConfig)

    def validate_version(self) -> bool:
        import re; return bool(re.match(r"^\d+\.\d+\.\d+$", self.version))

class BaseSkill(ABC):
    def __init__(self, metadata: SkillMetadata):
        self.metadata = metadata
        self._execution_count = 0; self._total_duration = 0.0
        self._error_count = 0; self._cache: Dict[str, Tuple[Any,float]] = {}
        if not metadata.validate_version():
            raise ValueError(f"Invalid SemVer: {metadata.version}")

    @property
    def llm_function_definition(self) -> Dict:
        return {"name": self.metadata.name, "description": self.metadata.description,
                "input_schema": {"type":"object",
                    "properties": {i.name:{"type":i.type,"description":i.description} for i in self.metadata.inputs},
                    "required": [i.name for i in self.metadata.inputs if i.required]}}

    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]: ...

    async def __call__(self, **kwargs) -> Dict[str, Any]:
        start = time.time()
        try:
            self._validate_inputs(kwargs)
            if self.metadata.cacheable:
                cached = self._check_cache(kwargs)
                if cached is not None: return cached
            result = await self._execute_with_retries(kwargs)
            if self.metadata.cacheable and result: self._store_cache(kwargs, result)
            self._update_metrics(time.time()-start, True)
            return result or {}
        except (SkillValidationError, SkillTimeoutError): self._update_metrics(time.time()-start, False); raise
        except Exception as e:
            self._update_metrics(time.time()-start, False)
            raise SkillExecutionError(f"Skill '{self.metadata.name}' failed: {e}")

    async def _execute_with_retries(self, kwargs):
        for attempt in range(self.metadata.max_retries):
            try: return await asyncio.wait_for(self.execute(**kwargs), timeout=self.metadata.timeout)
            except asyncio.TimeoutError:
                if attempt == self.metadata.max_retries-1: raise SkillTimeoutError(f"{self.metadata.name} timed out")
                await asyncio.sleep(0.5*(2**attempt))
            except Exception:
                if attempt == self.metadata.max_retries-1: raise
                await asyncio.sleep(0.1*(2**attempt))

    def _validate_inputs(self, kwargs):
        for inp in self.metadata.inputs:
            if inp.name in kwargs:
                ok, msg = inp.validate(kwargs[inp.name])
                if not ok: raise SkillValidationError(msg)
            elif inp.required: raise SkillValidationError(f"Required input missing: {inp.name}")

    def _check_cache(self, kwargs):
        key = json.dumps(kwargs, sort_keys=True, default=str)
        if key in self._cache:
            val, ts = self._cache[key]
            if self.metadata.cache_ttl is None or (time.time()-ts) < self.metadata.cache_ttl: return val
            del self._cache[key]
        return None

    def _store_cache(self, kwargs, result):
        self._cache[json.dumps(kwargs, sort_keys=True, default=str)] = (result, time.time())

    def _update_metrics(self, duration, success):
        self._execution_count += 1; self._total_duration += duration
        if not success: self._error_count += 1

    def get_metrics(self) -> Dict:
        avg = self._total_duration/self._execution_count if self._execution_count else 0
        return {"name":self.metadata.name,"executions":self._execution_count,
                "errors":self._error_count,"avg_duration_ms":avg*1000}

    def export_skill_file(self) -> str:
        inputs_md = "\n".join(f"- `{i.name}` ({i.type}): {i.description}" for i in self.metadata.inputs) or "_none_"
        return f"""---
name: "{self.metadata.name}"
version: "{self.metadata.version}"
category: "{self.metadata.category.value}"
author: "{self.metadata.author}"
mcp_server: true
---

## Purpose
{self.metadata.description}

## Inputs
{inputs_md}

## Output
{self.metadata.outputs.description}
"""
