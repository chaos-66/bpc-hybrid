# Safety Rules — bpc-hybrid

## 1. Allowed Path

The ONLY allowed project path is:

```
D:\Paper\experiment\bpc-hybrid
```

All file reads, writes, and operations MUST stay within this directory
and its subdirectories.

## 2. Forbidden Paths

The following paths (and all their subdirectories) MUST NOT be accessed:

- `C:\` (entire drive)
- `D:\` outside `D:\Paper\experiment\bpc-hybrid`
- `D:\Paper` (parent directory)
- `D:\Paper\experiment` (parent directory)
- `D:\AAAread`
- `D:\agent`
- `D:\environment`
- Desktop, Downloads, Documents
- WindowsApps, Program Files
- Python site-packages
- Any path not explicitly provided by the user

## 3. Forbidden Commands

The following commands (and any equivalent variants) are ABSOLUTELY FORBIDDEN:

- `Remove-Item -Recurse`
- `rmdir /s`
- `rd /s`
- `del /s`
- `git clean -fdx`
- `robocopy /MIR`
- `format`
- Cross-drive recursive delete/move
- Cross-directory recursive delete/move
- Bulk cleanup
- Directory wiping

If any operation might affect paths outside `D:\Paper\experiment\bpc-hybrid`,
it MUST be stopped immediately and reported.

## 4. GitHub Push Requirement

- Local commits alone do NOT constitute stage completion.
- Only a **successful GitHub push** marks a stage as complete.
- If `git push` fails, the stage is FAILED.
- No further development (R1+) is allowed after a push failure.

## 5. Secrets and Credentials

- `.env` files MUST NOT be read, printed, copied, or committed.
- API keys, GitHub tokens, and passwords MUST NOT be printed.
- The following are forbidden from Git:
  - `.env`, `.env.*`
  - `.venv/`
  - `outputs/`
  - `logs/`
  - Raw API responses

## 6. Data Integrity

- GDPR / BPMN / Sun dataset data MUST NOT be fabricated.
- Synthetic prototypes MUST NOT be presented as formal benchmarks.
- Claims about surpassing Sun or any prior work are forbidden.
- Claims about completing BPMN compliance checking are forbidden
  (until actually done).
- Claims about completing over-compliance detection are forbidden
  (until actually done).

## 7. Allowed Statements

The following factual statements are allowed:

- "Current completion is safe bootstrap."
- "Current project goal is to rebuild a runnable MVP."
- "Current main track is Sun-aligned GDPR + BPMN."
- "No real data is included at this stage."
- "No benchmark results are claimed at this stage."

## 8. Emergency Protocol

If any of the following are detected, STOP immediately and report:

- Current working directory is outside `D:\Paper\experiment\bpc-hybrid`
- Git remote points to an unexpected or non-GitHub URL
- `.env` or credential files appear in Git staging area
- Large-scale file changes or deletions are detected
- Unknown processes are modifying the project directory
- Files outside the project root are accessed or modified
