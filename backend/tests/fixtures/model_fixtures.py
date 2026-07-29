"""Deterministic provider fixtures shared by unit and browser integration tests."""

import json


def completion(calls, stop="tool_use"):
    return {
        "stop_reason": stop,
        "content": calls,
        "usage": {"input_tokens": 20, "output_tokens": 10},
    }


def call(name, params, identity="tool-1"):
    return {"type": "tool_use", "name": name, "input": params, "id": identity}


class ScriptedClient:
    def __init__(self, steps):
        self.steps = iter(steps)
        self.requests = []

    async def complete(self, messages, definitions, max_tokens=2048):
        self.requests.append(json.loads(json.dumps(messages)))
        step = next(self.steps)
        return step(messages) if callable(step) else step
