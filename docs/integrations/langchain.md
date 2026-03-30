# LangChain Integration

Add Pillar6 production infrastructure to your LangChain chains and agents.

## Installation

```bash
pip install pillar6[langchain]
```

## 5-Minute Setup

```python
from langchain.chains import LLMChain
from langchain_anthropic import ChatAnthropic
from langchain.prompts import PromptTemplate
from pillar6.wrappers.langchain import wrap_langchain

# Your existing LangChain code
llm = ChatAnthropic(model="claude-sonnet-4-20250514")
prompt = PromptTemplate.from_template("Explain {topic} in simple terms.")
chain = LLMChain(llm=llm, prompt=prompt)

# Add Pillar6 — one line
production_chain = wrap_langchain(chain)

# Use like normal
result = await production_chain.ainvoke({"topic": "quantum computing"})
```

## Full Example

```python
from pillar6 import Pillar6Config
from pillar6.config.models import SecurityConfig
from pillar6.wrappers.langchain import wrap_langchain

config = Pillar6Config(
    security=SecurityConfig(
        blocked_patterns=[r"ignore\s+instructions"],
    ),
)

production_chain = wrap_langchain(my_chain, config=config)
result = await production_chain.ainvoke({"query": "Research AI safety"})

# View what happened
events = await production_chain.traces.get_trace(production_chain.last_workflow_id)
for event in events:
    print(f"[{event.event_type}] {event.message}")
```

## What You Get

- **Distributed tracing** — every invocation is traced with timing
- **Input validation** — all string inputs are checked for prompt injection
- **Cost metrics** — duration tracking per invocation
- **Audit trail** — all calls are logged for compliance

## Advanced Configuration

```python
from pillar6 import Pillar6Config
from pillar6.config.models import ObservabilityConfig, SecurityConfig

config = Pillar6Config(
    security=SecurityConfig(
        max_input_length=50_000,
        enable_input_validation=True,
    ),
    observability=ObservabilityConfig(
        enable_tracing=True,
        enable_metrics=True,
    ),
)

production_chain = wrap_langchain(chain, config=config)
```
