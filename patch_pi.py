#!/usr/bin/env python3
"""Patch the installed Pi version's output budget for the Apple FM provider."""
from pathlib import Path

root = Path(__file__).parent / 'pi/node_modules/@earendil-works'
path = root / 'pi-ai/dist/api/simple-options.js'
old = 'const available = model.contextWindow - estimateContextTokens(context).tokens - CONTEXT_SAFETY_TOKENS;'
new = ("const safetyTokens = model.provider === 'apple-fm' ? 512 : CONTEXT_SAFETY_TOKENS;\n"
       '    const available = model.contextWindow - estimateContextTokens(context).tokens - safetyTokens;')
text = path.read_text()
if new in text:
    print('Pi Apple FM budget patch already installed')
elif text.count(old) == 1:
    path.write_text(text.replace(old, new))
    print('Installed Pi Apple FM budget patch')
else:
    raise SystemExit('Pi version changed; budget patch does not match. Inspect before updating.')

old_bundle = 'model.contextWindow-estimateContextTokens(context).tokens-CONTEXT_SAFETY_TOKENS'
new_bundle = "model.contextWindow-estimateContextTokens(context).tokens-(model.provider==='apple-fm'?512:CONTEXT_SAFETY_TOKENS)"
matches = [p for p in (root / 'pi-coding-agent/dist/bundle').rglob('*.js')
           if old_bundle in p.read_text() or new_bundle in p.read_text()]
if not matches:
    raise SystemExit('Pi bundle changed; no budget implementation found.')
for bundle in matches:
    content = bundle.read_text()
    if old_bundle in content:
        if content.count(old_bundle) != 1:
            raise SystemExit('Unexpected number of bundle budget implementations.')
        bundle.write_text(content.replace(old_bundle, new_bundle))
        print(f'Installed Pi bundled Apple FM budget patch: {bundle.name}')
