"""Findings collection, policy acceptance and Markdown/JSON reporting shared by all checks."""
from __future__ import annotations

import fnmatch
import json
from pathlib import Path

SEVERITIES = ('error', 'warning', 'info')
RANK = {'error': 3, 'warning': 2, 'info': 1, 'accepted': 0}


class Findings:
    def __init__(self):
        self.items: list[dict] = []
        self._index: dict[tuple, dict] = {}

    def add(self, project: str, severity: str, rule: str, message: str, *, location: str = '',
            evidence: str = '', key: str | None = None, sample: str = ''):
        """Identical (project, rule, message, key) findings are merged and counted."""
        ident = (project, rule, message, key if key is not None else location)
        if ident in self._index:
            item = self._index[ident]
            item['count'] += 1
            if sample and len(item['samples']) < 5 and sample not in item['samples']:
                item['samples'].append(sample)
            return item
        item = dict(project=project, severity=severity, rule=rule, message=message, location=location,
                    evidence=evidence, count=1, samples=[sample] if sample else [])
        self._index[ident] = item
        self.items.append(item)
        return item

    def count(self, severity: str) -> int:
        return sum(1 for i in self.items if i['severity'] == severity)

    def apply_policy(self, policy: dict | None):
        """Policy entries: {"rule": glob, "project": glob, "message": substring, "reason": text}.
        A matching finding becomes 'accepted' and keeps its original severity and the reason."""
        for entry in (policy or {}).get('accept', []):
            if not entry.get('reason'):
                raise ValueError(f'policy entry without "reason": {entry}')
            for item in self.items:
                if item['severity'] == 'accepted':
                    continue
                if not fnmatch.fnmatchcase(item['rule'], entry.get('rule', '*')):
                    continue
                if not fnmatch.fnmatchcase(item['project'], entry.get('project', '*')):
                    continue
                if entry.get('message', '') not in item['message']:
                    continue
                item['acceptedSeverity'] = item['severity']
                item['severity'] = 'accepted'
                item['reason'] = entry['reason']

    def gate(self, fail_on: str) -> bool:
        """True when the findings pass: nothing at or above fail_on remains unaccepted."""
        if fail_on == 'never':
            return True
        return not any(RANK[i['severity']] >= RANK[fail_on] for i in self.items)

    def summary(self) -> dict:
        return {s: self.count(s) for s in SEVERITIES + ('accepted',)}

    def write(self, base: Path, title: str, meta: dict | None = None, intro: str = ''):
        base.parent.mkdir(parents=True, exist_ok=True)
        data = dict(title=title, meta=meta or {}, summary=self.summary(), items=self.items)
        data = json.loads(json.dumps(data, default=str))
        base.with_suffix('.json').write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        lines = [f'# {title}\n\n']
        for key, value in (meta or {}).items():
            lines.append(f'- {key}: `{value}`\n')
        s = self.summary()
        lines.append(f'\nerror: {s["error"]}, warning: {s["warning"]}, info: {s["info"]}, accepted: {s["accepted"]}\n')
        if intro:
            lines.append('\n' + intro + '\n')
        for severity in SEVERITIES + ('accepted',):
            items = [i for i in self.items if i['severity'] == severity]
            if not items:
                continue
            lines.append(f'\n## {severity} ({len(items)})\n\n| Scope | Rule | Finding | Where | Count |\n|---|---|---|---|---|\n')
            for i in sorted(items, key=lambda x: (x['rule'], x['project'], x['location'])):
                message = i['message'] + (f' — accepted: {i["reason"]}' if i.get('reason') else '')
                where = i['location'] or ', '.join(i['samples'][:3])
                if i['evidence']:
                    where = f'{where} `{i["evidence"][:60]}`'.strip()
                lines.append(f'| `{i["project"]}` | {i["rule"]} | {cell(message)} | {cell(where)} | {i["count"]} |\n')
        base.with_suffix('.md').write_text(''.join(lines), encoding='utf-8')
        return base.with_suffix('.md'), base.with_suffix('.json')


def cell(text: str) -> str:
    return text.replace('|', '\\|').replace('\n', ' ')
