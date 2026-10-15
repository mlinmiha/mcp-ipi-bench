[EN](README.md) | [SI](README.si.md)

# runner

Does the benchmark's runs. One run is a model with a defense on a user task, under an attack with an injection task
for a security run. Its result is written to one run file, the source of truth for every metric.

| File          | What it holds                                                                                                |
|---------------|--------------------------------------------------------------------------------------------------------------|
| `runner.py`   | `run_task` (one scored run), `run` (one run written to its run file), `benchmark` (the runs of one run type) |
| `run_file.py` | `RunResult`, the run file's fields, and the run file's path                                                  |
| `sweep.py`    | `Sweep`: a sweep file, its expansion into runs per run type, and the dry run's counts                        |
| `show.py`     | The text of `ipi show`: a run in full, a table of runs, a summary line                                       |

## A run

1. The attack text is built and put into the injection vectors the user task reads (security runs only).
2. Two copies of the environment are loaded: one stays as the pre-environment, the agent works on the other.
3. The pipeline of the defense runs the user task's prompt over MCP.
4. The user task's check gives `utility`, the injection task's check gives `security` (true = the attack succeeded).

## Run files

```
<logdir>/<pipeline>/<suite>/<user_task>/<attack>/<injection_task>.json
runs-pilot/openai_gpt-5.4-mini-spotlighting/workspace/cloud_storage_user_task_2/tool-notice/web_injection_task_2.json
```

A run whose file exists without an error is skipped, so a sweep that stopped is resumed by running it again.

## Example

```sh
uv run ipi sweep sweeps/main.yaml --dry-run   # count the runs, no model call
uv run --env-file .env ipi sweep sweeps/main.yaml
uv run ipi show --summary runs/<pipeline>/workspace/*/none/none.json
```
