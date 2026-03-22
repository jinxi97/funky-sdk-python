# funky-sdk

SDK for connecting a Funky workspace to agents through the backend API.

## Install (uv)

```bash
uv sync --group dev
```

## Usage

```python
from google.adk.agents import Agent
from funky import Workspace

# Create a workspace (blocks until ready)
ws = Workspace.create()

# Define the tool using your simple API
def run_remote_code(command: str):
    """Executes bash commands in the secure Funky workspace."""
    result = ws.execute(command)
    return result.stdout

# Attach to Agent
agent = Agent(tools=[run_remote_code])

# Delete workspace when done
message = ws.delete()
print(message)
```

## API behavior

- `Workspace.create(...)` calls `POST /workspace`, then streams `GET /workspace/{claim_name}/events` via SSE until the workspace is ready.
- `Workspace.execute(command)` calls `POST /workspaces/{claim_name}/exec?command=...`.
- `Workspace.delete()` calls `DELETE /workspaces/{claim_name}` and returns the backend response string.
- The workspace exposes `claim_name`, `namespace`, and `pod_name` after creation.
- Responses are exposed via `ExecutionResult`:
  - `stdout`: command output from backend
  - `stderr`: currently empty string
  - `exit_code`: currently `0` on successful API response
