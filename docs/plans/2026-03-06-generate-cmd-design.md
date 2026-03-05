# Generate Command Design

## Goal

Extract AI figure generation into a standalone `wenqiao generate` subcommand with async concurrency, range selection, and ai-done writeback; `convert --generate-figures` calls the same async backend.

---

## Architecture

**New/modified files:**

| File | Action |
|------|--------|
| `src/wenqiao/generate_cmd.py` | New — `generate` Click command |
| `src/wenqiao/genfig.py` | Add `run_generate_figures_async()` and `async_generate()` default |
| `src/wenqiao/genfig_openai.py` | Add `async_generate()` override with `openai.AsyncOpenAI` |
| `src/wenqiao/cli.py` | Register `generate_cmd`; add `--concurrency` to `convert` |

**Call flow:**

```
generate_cmd
  └─ asyncio.run(run_generate_figures_async(jobs, runner, concurrency, force))
       └─ asyncio.Semaphore(concurrency)
       └─ asyncio.gather(*[_run(job) for job in jobs])
            └─ runner.async_generate(job)  ← OpenAIFigureRunner or base default
```

`convert --generate-figures` uses the same `run_generate_figures_async()` path.

---

## CLI Interface

### `wenqiao generate INPUT [OPTIONS]`

```
Arguments:
  INPUT   Path to .mid.md file

Options:
  --figures-config PATH   TOML config for AI backend (API key, model, URL)
  --model TEXT            Override model from config
  --base-url TEXT         Override API base URL from config
  --api-key TEXT          Override API key (also reads WENQIAO_API_KEY env var)
  --type [openai]         Backend type (default: openai)
  --concurrency INT       Max concurrent generations (default: 4)
  --start-id INT          Start figure index, 1-based (default: 1)
  --end-id INT            End figure index, inclusive (default: last)
  --force                 Re-generate even if output file exists
  --no-writeback          Skip writing <!-- ai-done: true --> to source file
```

### `wenqiao convert INPUT [OPTIONS]` — additions

```
  --concurrency INT       Max concurrent figure generations (default: 4)
  (existing) --figures-config PATH
  (existing) --force-regenerate
```

**Option priority:** CLI flag > `WENQIAO_API_KEY` env var > TOML config > default.

Inline overrides (`--model`, `--base-url`, `--api-key`, `--type`) live only on `generate` — `convert` uses TOML only.

---

## FigureRunner Async Interface

`genfig.py` ABC gains a default async method:

```python
class FigureRunner(ABC):
    @abstractmethod
    def generate(self, job: FigureJob) -> Path: ...

    async def async_generate(self, job: FigureJob) -> Path:
        """Default: wrap sync generate() in a thread (默认在线程中调用同步版本)."""
        return await asyncio.to_thread(self.generate, job)
```

`OpenAIFigureRunner` overrides with true async:

```python
async def async_generate(self, job: FigureJob) -> Path:
    client = openai.AsyncOpenAI(api_key=..., base_url=...)
    response = await client.images.generate(...)
    # save to output path, return path
```

`run_generate_figures_async()` in `genfig.py`:

```python
async def run_generate_figures_async(
    jobs: list[FigureJob],
    runner: FigureRunner,
    concurrency: int = 4,
    force: bool = False,
    writeback: bool = True,
    echo: Callable[[str], None] = print,
) -> tuple[int, int]:   # (success, fail)
    sem = asyncio.Semaphore(concurrency)

    async def _run(job: FigureJob) -> bool:
        if not force and job.output_path.exists():
            echo(f"[generate] skip {job.label} (output exists)")
            return True
        async with sem:
            path = await runner.async_generate(job)
        if writeback and job.source_file is not None:
            _write_ai_done(job.source_file, job.label)
        return path is not None

    results = await asyncio.gather(*[_run(j) for j in jobs], return_exceptions=True)
    success = sum(1 for r in results if r is True)
    fail = len(results) - success
    return success, fail
```

---

## ai-done Writeback

After a successful generation, append `<!-- ai-done: true -->` on the line immediately after the figure's `<!-- label: LABEL -->` line in the source `.mid.md`.

Strategy: simple line scan — find the label marker, insert after it. `FigureJob` carries `source_file: Path | None` and `label: str`.

```python
def _write_ai_done(source_path: Path, label: str) -> None:
    """Write ai-done marker after the matching label comment (写入 ai-done 标记)."""
    lines = source_path.read_text(encoding="utf-8").splitlines(keepends=True)
    out: list[str] = []
    for line in lines:
        out.append(line)
        if f"label: {label}" in line and "<!--" in line:
            # Only insert if not already present (避免重复写入)
            marker = "<!-- ai-done: true -->\n"
            if out and marker not in out:
                out.append(marker)
    source_path.write_text("".join(out), encoding="utf-8")
```

Skip writeback if `--no-writeback` flag is set or if `job.source_file is None`.

---

## convert Integration

`convert_cmd` gains `--concurrency INT` option. When `--generate-figures` is set, it calls `asyncio.run(run_generate_figures_async(...))` instead of the old synchronous `run_generate_figures()`. The old synchronous function is kept for backward compatibility but no longer called by `convert`.

---

## Testing

- Unit: `test_genfig_async.py` — mock runner, test semaphore limits, skip logic, writeback
- Unit: `test_generate_cmd.py` — Click CLI tests with mock runner
- Integration: `test_lint.py`-style with temp `.mid.md` files
- All new tests use `--no-writeback` or mock `source_file=None` to avoid file mutation in tests
