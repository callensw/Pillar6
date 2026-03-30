# ReAct Pattern

The ReAct (Reasoning + Acting) pattern implements a think-act-observe loop
where the agent reasons about each step before taking action.

## When to Use

- Tasks requiring multi-step reasoning with tool use
- Problems where the agent needs to adapt based on intermediate results
- Scenarios where transparency of reasoning is important

## How It Works

```
1. THINK   -- LLM reasons about the current state
2. ACT     -- Execute a tool call
3. OBSERVE -- Add tool result to context
4. Repeat until Final Answer or max_steps reached
```

The LLM is prompted to respond in a structured format:

```
Thought: I need to look up the weather in London.
Action: get_weather
Action Input: {"city": "London"}
```

Or when it has the answer:

```
Thought: I now have all the information I need.
Final Answer: The weather in London is cloudy and 15C.
```

## Full Example

```python
import asyncio
from pillar6.agents.patterns import ReActAgent, ReActConfig
from pillar6.config.models import Pillar6Config, SecurityConfig
from pillar6.core.eval import MockLLMAdapter

async def get_weather(city: str) -> str:
    return f"{city}: Sunny, 25C"

# Mock LLM that simulates ReAct responses
llm = MockLLMAdapter(responses={
    "weather": (
        'Thought: I need to check the weather.\n'
        'Action: get_weather\n'
        'Action Input: {"city": "London"}'
    ),
    "Observation": (
        'Thought: I now know the weather.\n'
        'Final Answer: The weather in London is Sunny, 25C.'
    ),
})

agent = ReActAgent(
    react_config=ReActConfig(max_steps=5),
    config=Pillar6Config(security=SecurityConfig(default_deny=False)),
    llm=llm,
)

agent.tool_registry.register(
    "get_weather",
    get_weather,
    {
        "properties": {"city": {"type": "string"}},
        "required": ["city"],
    },
)

result = asyncio.run(agent.run("What is the weather in London?"))
print(result)
```

## Configuration

```python
from pillar6.agents.patterns import ReActConfig

config = ReActConfig(
    max_steps=10,              # Maximum reasoning steps
    thought_prefix="Thought:", # Prefix for thought lines
    action_prefix="Action:",   # Prefix for action lines
    action_input_prefix="Action Input:",
    final_answer_prefix="Final Answer:",
)
```

## Tips

- **Set a reasonable `max_steps`** to prevent infinite loops. 5-10 is typical.
- **Register all tools** the agent might need before calling `run()`.
- **Grant permissions** if using `default_deny=True` in security config.
- **Check traces** after runs to understand the agent's reasoning chain.
