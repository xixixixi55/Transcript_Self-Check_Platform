"""Regression tests for the strict documentation task-reference rule."""

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _extract_completed_refs(content: str) -> list[str]:
    probe = (
        "import { getCompletedTaskFileReferences } from './scripts/check-docs-utils.ts';"
        f"console.log(JSON.stringify(getCompletedTaskFileReferences({json.dumps(content)})));"
    )
    result = subprocess.run(
        ["npx.cmd", "tsx", "-e", probe],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_strict_task_file_refs_only_validate_completed_entries():
    refs = _extract_completed_refs(
        """
- [ ] `packages/backend/app/services/future_phase.py`
- [x] `packages/backend/app/services/case_draft_service.py`
- [X] `openspec/specs/data-model.md`
```text
- [x] `packages/backend/app/services/inside_code_block.py`
```
"""
    )

    assert refs == [
        "packages/backend/app/services/case_draft_service.py",
        "openspec/specs/data-model.md",
    ]
