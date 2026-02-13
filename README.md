# funky-sdk (fake v0)

This is a deterministic fake SDK for connecting a Funky workspace to agents.

## Install (uv)

```bash
uv sync --group dev
```

## Usage

```python
from google.adk.agents import Agent
from funky import Workspace

# Initialize your SDK
ws = Workspace.create()

# Define the tool using your simple API
def run_remote_code(command: str):
    """Executes bash commands in the secure Funky workspace."""
    result = ws.execute(command)
    return result.stdout

# Attach to Agent
agent = Agent(tools=[run_remote_code])
```

## Fake behavior (v0)

- `Workspace.execute(command)` does not execute shell commands.
- It always returns a structured result with:
  - `stdout = "Command executed!"`
  - `stderr = ""`
  - `exit_code = 0`
