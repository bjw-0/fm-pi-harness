#!/usr/bin/env python3
"""Try bounded single-file edits with Apple's fm, recording verifiable evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid


def run(args, **kwargs):
    return subprocess.run(args, text=True, capture_output=True, **kwargs)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo', required=True, type=Path)
    p.add_argument('--file', required=True, help='Tracked file relative to repository root')
    p.add_argument('--task', required=True)
    p.add_argument('--check', required=True, help='Trusted shell command run in the worktree')
    p.add_argument('--attempts', type=int, default=3)
    p.add_argument('--timeout', type=int, default=120, help='Seconds per model or check call')
    p.add_argument('--max-source-chars', type=int, default=6000)
    p.add_argument('--output', type=Path, default=Path('runs'))
    a = p.parse_args()
    if a.attempts < 1 or a.timeout < 1:
        p.error('attempts and timeout must be positive')
    repo = a.repo.resolve()
    root = run(['git', '-C', str(repo), 'rev-parse', '--show-toplevel'])
    if root.returncode:
        p.error('repo must be a Git repository')
    repo = Path(root.stdout.strip())
    relative = Path(a.file)
    if relative.is_absolute() or '..' in relative.parts:
        p.error('file must be a repository-relative path')
    tracked = run(['git', '-C', str(repo), 'ls-files', '--error-unmatch', '--', str(relative)])
    if tracked.returncode:
        p.error('file must be tracked')
    head = run(['git', '-C', str(repo), 'rev-parse', 'HEAD']).stdout.strip()
    out = (a.output.resolve() / (time.strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8]))
    out.mkdir(parents=True)
    worktree = out / 'worktree'
    added = run(['git', '-C', str(repo), 'worktree', 'add', '--detach', str(worktree), head])
    if added.returncode:
        raise RuntimeError(added.stderr)
    target = worktree / relative
    if not target.is_file() or not target.resolve().is_relative_to(worktree.resolve()) or target.is_symlink():
        raise ValueError('target must be a regular file inside the worktree')
    source = target.read_text()
    if len(source) > a.max_source_chars:
        raise ValueError('target exceeds source limit; choose a smaller file or adjust --max-source-chars')
    metadata = {'repo': str(repo), 'head': head, 'file': str(relative), 'task': a.task,
                'check': a.check, 'attempts': a.attempts, 'timeout': a.timeout,
                'source_sha256': hashlib.sha256(source.encode()).hexdigest(), 'results': []}
    def save():
        (out / 'run.json').write_text(json.dumps(metadata, indent=2) + '\n')
    save()
    # A passing candidate check is more informative when the same check failed
    # before the edit. Record the baseline without requiring a failing test:
    # some tasks deliberately improve code while preserving existing behavior.
    try:
        baseline = run(['/bin/sh', '-c', a.check], cwd=worktree, timeout=a.timeout)
        baseline_output = baseline.stdout + '\n' + baseline.stderr
        metadata['baseline'] = {'exit': baseline.returncode}
    except subprocess.TimeoutExpired:
        baseline_output = 'Baseline check timed out.\n'
        metadata['baseline'] = {'status': 'timeout'}
    (out / 'baseline.check.txt').write_text(baseline_output)
    save()
    feedback = ''
    instructions = ('Return only the complete replacement file. No markdown fences or explanation. '
                    'Make the smallest change satisfying the task; preserve unrelated behavior.')
    for i in range(1, a.attempts + 1):
        prompt = f'Task: {a.task}\nFile: {relative}\nCurrent file:\n{source}\n'
        if feedback:
            prompt += f'Previous check failed. Fix the file. Output excerpt:\n{feedback}\n'
        start = time.monotonic()
        try:
            model = run(['fm', 'respond', '--model', 'system', '--no-stream', '--greedy',
                         '--instructions', instructions], input=prompt, timeout=a.timeout)
        except subprocess.TimeoutExpired:
            metadata['results'].append({'attempt': i, 'status': 'model_timeout'})
            save()
            break
        (out / f'attempt-{i}.model.txt').write_text(model.stdout)
        (out / f'attempt-{i}.model.stderr.txt').write_text(model.stderr)
        result = {'attempt': i, 'model_exit': model.returncode, 'model_seconds': round(time.monotonic()-start, 3)}
        metadata['results'].append(result)
        candidate = model.stdout
        fenced = re.fullmatch(r'\s*```[^\n]*\n(.*?)\n```\s*', candidate, re.DOTALL)
        if fenced:
            candidate = fenced.group(1) + '\n'
        if model.returncode or not candidate.strip() or candidate.lstrip().startswith('```'):
            result['status'] = 'invalid_model_output'
            save()
            break
        target.write_text(candidate)
        diff = run(['git', '-C', str(worktree), 'diff', '--', str(relative)]).stdout
        (out / f'attempt-{i}.patch').write_text(diff)
        try:
            check = run(['/bin/sh', '-c', a.check], cwd=worktree, timeout=a.timeout)
            full_output = check.stdout + '\n' + check.stderr
            feedback = full_output[-3000:]
            result.update(check_exit=check.returncode, status='passed' if check.returncode == 0 and diff else 'failed')
        except subprocess.TimeoutExpired:
            feedback = 'Check timed out.'
            full_output = feedback
            result.update(status='check_timeout')
        (out / f'attempt-{i}.check.txt').write_text(full_output)
        save()
        print(f"Attempt {i}: {result['status']}", flush=True)
        if result['status'] == 'passed':
            break
        source = candidate
    print(f'Evidence and worktree: {out}')
    return 0 if metadata['results'] and metadata['results'][-1]['status'] == 'passed' else 1


if __name__ == '__main__':
    sys.exit(main())
