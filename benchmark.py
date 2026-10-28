#!/usr/bin/env python3
"""Compare Pi's standard prompt with a compact prompt on disposable tasks."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parent
COMPACT = ('You are a coding assistant. Inspect relevant files, make focused changes, '
           'run appropriate checks, and report results and uncertainty concisely.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repeats', type=int, default=3)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error('repeats must be positive')
    records = []
    for iteration in range(args.repeats):
        for variant in ('standard', 'compact'):
            for task in ('read', 'edit'):
                with tempfile.TemporaryDirectory(prefix='fm-pi-bench-') as directory:
                    path = Path(directory)
                    (path / 'calc.py').write_text('def add(a, b):\n    return a - b\n')
                    (path / 'check.py').write_text('from calc import add\nassert add(2, 3) == 5\nassert add(-2, 1) == -1\n')
                    tools = 'read' if task == 'read' else 'read,edit,bash'
                    question = ('Read calc.py and say what add returns.' if task == 'read' else
                                'Fix calc.py so add returns a + b. Run python3 check.py.')
                    command = ['bash', str(ROOT / 'fm-pi'), '--no-mcp', '--no-context-files',
                               '--no-session', '--tools', tools, '--mode', 'json']
                    if variant == 'compact':
                        command += ['--system-prompt', COMPACT]
                    else:
                        command += ['--standard-prompt']
                    command += ['-p', question]
                    start = time.monotonic()
                    try:
                        result = subprocess.run(command, cwd=path, capture_output=True, text=True, timeout=90)
                        events = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
                        calls = [e.get('toolName') for e in events if e.get('type') == 'tool_execution_start']
                        ends = [e['message'] for e in events if e.get('type') == 'message_end' and e.get('message', {}).get('role') == 'assistant']
                        answer = ' '.join(x.get('text', '') for e in ends for x in e.get('content', []) if x.get('type') == 'text')
                        if task == 'read':
                            success = 'read' in calls and ('a - b' in answer or 'subtract' in answer.lower() or 'difference' in answer.lower())
                        else:
                            check = subprocess.run(['python3', 'check.py'], cwd=path, capture_output=True, timeout=10)
                            success = 'edit' in calls and 'bash' in calls and check.returncode == 0
                        records.append({'iteration': iteration, 'variant': variant, 'task': task,
                                        'success': success, 'seconds': round(time.monotonic()-start, 2),
                                        'calls': calls, 'exit': result.returncode, 'answer': answer[:300]})
                    except (subprocess.TimeoutExpired, ValueError) as exc:
                        records.append({'iteration': iteration, 'variant': variant, 'task': task,
                                        'success': False, 'error': type(exc).__name__})
                    print(json.dumps(records[-1]), flush=True)


if __name__ == '__main__':
    main()
