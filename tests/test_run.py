from __future__ import annotations

import time

from funky import Workspace


def main() -> None:
    workspace = Workspace.create()
    print("workspace_claim_name:", workspace.claim_name)
    print("workspace_namespace:", workspace.namespace)

    result = workspace.execute("echo 'hello world' > hello.txt && cat hello.txt")
    print("stdout:", result.stdout.strip())
    print("stderr:", result.stderr.strip())
    print("exit_code:", result.exit_code)

    # time.sleep(5)
    snapshot_name = workspace.snapshot()
    print("snapshot_name:", snapshot_name)

    restored_workspace = Workspace.restore(
        workspace.claim_name,
        workspace.namespace,
        snapshot_name,
    )
    print("restored_workspace_claim_name:", restored_workspace.claim_name)
    print("restored_workspace_namespace:", restored_workspace.namespace)

    restored_result = restored_workspace.execute(
        "if [ -f hello.txt ]; then cat hello.txt; else echo 'missing'; fi"
    )
    print("restored_stdout:", restored_result.stdout.strip())
    print("restored_stderr:", restored_result.stderr.strip())
    print("restored_exit_code:", restored_result.exit_code)


if __name__ == "__main__":
    main()
