# Apple FM + Pi experimental harness

Use Apple's on-device Foundation Models CLI with the Pi coding agent. This is an experiment, not a production-ready coding agent: its small context window and output quality limit complex tasks. A small read/edit/test fixture passed, but real repository and MCP workflows have not been validated reliably.

## Requirements

- macOS 27 with Apple Intelligence enabled and the `fm` CLI available. Accept Apple's CLI terms with `sudo fm license` if prompted.
- Node.js and npm, Python 3, Git, and curl.
- A compatible Pi package: the checked-in npm lock file pins the version tested. Pi is installed locally, not globally.

The pinned Pi dependency tree reported npm advisories in `undici` on 2026-10-28, including high-severity findings. Review `npm audit --omit=dev` and the advisories before use; a dependency update also requires retesting the compatibility patch. Avoid exposing the local model endpoint to other machines.

## Install and run

```sh
git clone https://github.com/bjw-0/fm-pi-harness.git
cd fm-pi-harness
npm ci --ignore-scripts --prefix pi
bash ./fm-pi
```

Launch from a repository to work on it: `cd /path/to/repo` followed by `bash /path/to/fm-pi-harness/fm-pi`. Pi can edit files and run shell commands with your user permissions; start in a disposable checkout and review its work. The launcher binds `fm serve` to loopback port 19761 and reuses any service already listening there; only use a trusted local endpoint. It stops a server it started when Pi exits.

Pi reserves 4096 context tokens by default, leaving a 4096-token model only one output token. `patch_pi.py` applies a provider-specific 512-token safety margin to the pinned Pi installation, failing if the code no longer matches. Pi's context estimate is not Apple's exact tokenizer; the margin and compaction settings do not guarantee that long prompts fit. Start small, limit tool output, and restart or compact if context overflows. Updating Pi requires revalidating the patch.

The launcher uses a short coding prompt to leave more room for the task and tools. Pass `--standard-prompt` to restore Pi's default prompt, or `--system-prompt 'your instructions'` to supply your own. `python3 benchmark.py` compares the two prompts on disposable read and edit/test fixtures; it makes model calls and reports per-run timing and checks. These small tests are not a measure of real-world agent reliability.

The launcher uses the local `pi-config` directory, so it does not overwrite a user's existing Pi configuration. Add your own MCP configuration there following [Pi's MCP documentation](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/mcp.md). MCP calls, long conversations, and model correctness are not guaranteed by the fixture test. Never commit credentials or session logs.

## Bounded single-file experiment

`fm_research.py` runs a baseline check in a detached worktree, asks the model to replace a single tracked file, and checks the edit; it saves logs and diffs. It uses committed HEAD, not uncommitted changes. Example arguments must be replaced with real paths and a trusted test command:

```sh
python3 /path/to/fm-pi-harness/fm_research.py \
  --repo /path/to/repo --file relative/path.py \
  --task 'Describe one small change' --check 'your test command' \
  --output /path/to/evidence
```

The check and generated code run with your permissions; a worktree is not a sandbox. A passing check is evidence only for what that check covers. Runs retain their worktrees for inspection; remove them with `git -C /path/to/repo worktree remove /path/to/run/worktree` once their changes are no longer needed.
