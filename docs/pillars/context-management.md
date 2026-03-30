# Context Management

The Context Management pillar handles everything related to the agent's context
window: token budgets, message priorities, eviction, compression, and
multi-agent isolation.

## Key Concepts

### Priority Buckets

Every message belongs to one of four priority levels:

| Priority | Description | Eviction order |
|----------|-------------|----------------|
| `SYSTEM` | System prompts | Never evicted |
| `RECENT` | Recent conversation messages | Evicted third |
| `RETRIEVED` | RAG / retrieved context | Evicted second |
| `EPHEMERAL` | Temporary / scratch data | Evicted first |

When the token budget is exceeded, messages are evicted starting from the
lowest priority (EPHEMERAL) upward. System messages are never evicted.

### Token Counting

Pillar6 uses a `TokenCounter` protocol so you can plug in any counting strategy:

```python
from pillar6.core.context import WordBasedTokenCounter

counter = WordBasedTokenCounter()
tokens = counter.count("Hello, how are you?")  # ~6 tokens
```

The default `WordBasedTokenCounter` estimates tokens as `max(1, int(words * 1.3 + 0.5))`.

## Configuration

```python
from pillar6.config.models import ContextConfig

config = ContextConfig(
    default_token_budget=4096,
    compression_threshold=0.8,     # Compress at 80% usage
    max_messages=100,
    system_budget_fraction=0.20,   # 20% for system messages
    recent_budget_fraction=0.40,   # 40% for recent messages
    retrieved_budget_fraction=0.25, # 25% for retrieved context
    ephemeral_budget_fraction=0.15, # 15% for ephemeral data
    compression_keep_recent=5,     # Keep 5 most recent during compression
)
```

## Usage

### Basic Context Operations

```python
from pillar6.core.context import DefaultContextManager
from pillar6.types import Priority

ctx = DefaultContextManager()

# Allocate a budget for an agent
await ctx.allocate("agent-1", token_budget=4096)

# Inject messages at different priorities
await ctx.inject("agent-1", "You are a helpful assistant.", Priority.SYSTEM)
await ctx.inject("agent-1", "What is 2+2?", Priority.RECENT)

# Retrieve ordered context
messages = await ctx.get_context("agent-1")
# Returns: [system message, recent message]
```

### Compression

When the context grows large, compress older messages:

```python
await ctx.compress("agent-1")
# Keeps the 5 most recent messages, replaces older ones with a summary
```

You can provide a custom summariser:

```python
async def my_summarizer(messages):
    return "Summary: " + "; ".join(m.content[:50] for m in messages)

await ctx.compress("agent-1", summarizer=my_summarizer)
```

### Multi-Agent Isolation

Each agent gets its own isolated context. Messages injected for one agent
are invisible to others:

```python
await ctx.allocate("agent-1", 4096)
await ctx.allocate("agent-2", 4096)

await ctx.inject("agent-1", "Secret info", Priority.RECENT)

msgs_1 = await ctx.get_context("agent-1")  # Contains "Secret info"
msgs_2 = await ctx.get_context("agent-2")  # Empty
```

### Snapshots

Save and restore context state:

```python
snapshot = await ctx.snapshot("agent-1")
# ... later ...
await ctx.restore(snapshot)
```
