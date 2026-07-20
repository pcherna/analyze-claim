import os

# The Anthropic provider demands a key at import time; tests never call it
# (agent.override + ALLOW_MODEL_REQUESTS below), so a dummy suffices.
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-never-used")

import pytest
from fastapi.testclient import TestClient
from pydantic_ai import models
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from app.main import app

# Hard guard: any attempt to reach a real model provider raises.
models.ALLOW_MODEL_REQUESTS = False


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def extraction_model(output: dict) -> FunctionModel:
    """A FunctionModel that always returns `output` as the extraction result."""

    def handler(messages, info: AgentInfo) -> ModelResponse:
        tool_name = info.output_tools[0].name
        return ModelResponse(parts=[ToolCallPart(tool_name=tool_name, args=output)])

    return FunctionModel(handler)
