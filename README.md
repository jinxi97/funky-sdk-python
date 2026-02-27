# funky-sdk

SDK for connecting a Funky workspace to agents through the backend API.

## Install (uv)

```bash
uv sync --group dev
```

## Usage

Set your API secret first:

```bash
export FUNKY_API_SECRET="your-secret"
```

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

# Delete workspace when done
message = ws.delete()
print(message)
```

You can also pass the secret directly:

```python
ws = Workspace.create(api_secret="your-secret")
```

## API behavior

- `Workspace.create(...)` calls `POST /workspaces` and stores the returned `workspace_id`.
- `Workspace.execute(command)` calls `POST /workspaces/{workspace_id}/exec?command=...`.
- `Workspace.delete()` calls `DELETE /workspaces/{workspace_id}` and returns the backend response string.
- Responses are exposed via `ExecutionResult`:
  - `stdout`: command output from backend
  - `stderr`: currently empty string
  - `exit_code`: currently `0` on successful API response
