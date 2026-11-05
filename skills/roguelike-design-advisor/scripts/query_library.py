#!/usr/bin/env python3
"""Read the bundled design library without loading every entry into a prompt."""

import argparse
import json
import sys
from pathlib import Path

LIBRARY_PATH = Path(__file__).resolve().parents[1] / 'references' / 'library.json'
TEXT_FIELDS = ('name', 'type', 'status', 'summary', 'trigger', 'effect', 'cost',
               'synergy', 'risk', 'source', 'notes')


def load_library():
    data = json.loads(LIBRARY_PATH.read_text(encoding='utf-8-sig'))
    if data.get('schema') != 'roguelike-atlas' or data.get('version') != 2:
        raise ValueError('Expected roguelike-atlas version 2.')
    entries = data.get('entries')
    if not isinstance(entries, list) or not entries:
        raise ValueError('Library entries must be a non-empty array.')
    by_id = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError('Each entry must be an object.')
        identifier = entry.get('id')
        if not isinstance(identifier, str) or not identifier.strip() or identifier in by_id:
            raise ValueError(f'Invalid or duplicate entry ID: {identifier!r}')
        for key in TEXT_FIELDS:
            if not isinstance(entry.get(key), str):
                raise ValueError(f'{identifier}: {key} must be text.')
        if not entry['name'].strip() or not entry['summary'].strip():
            raise ValueError(f'{identifier}: name and summary must not be empty.')
        if entry['type'] not in ('机制', '技能'):
            raise ValueError(f'{identifier}: unsupported type.')
        if entry['status'] not in ('灵感', '待验证', '已验证'):
            raise ValueError(f'{identifier}: unsupported design status.')
        for key in ('tags', 'relations', 'mechanismIds'):
            values = entry.get(key)
            if not isinstance(values, list) or any(not isinstance(v, str) or not v.strip() for v in values):
                raise ValueError(f'{identifier}: {key} must be an array of non-empty strings.')
            if len(values) != len(set(values)):
                raise ValueError(f'{identifier}: duplicate {key}.')
        if 'activationOptions' in entry and not isinstance(entry['activationOptions'], str):
            raise ValueError(f'{identifier}: activationOptions must be text.')
        if entry['type'] == '机制' and entry['mechanismIds']:
            raise ValueError(f'{identifier}: a mechanism cannot contain skill composition.')
        by_id[identifier] = entry
    for entry in entries:
        for ref in entry['relations'] + entry['mechanismIds']:
            if ref == entry['id'] or ref not in by_id:
                raise ValueError(f'{entry["id"]}: invalid reference {ref!r}.')
        for ref in entry['mechanismIds']:
            if by_id[ref]['type'] != '机制':
                raise ValueError(f'{entry["id"]}: composition target {ref!r} is not a mechanism.')
    return entries, by_id


def search(entries, query='', kind=None, tags=()):
    words = query.casefold().split()
    ranked = []
    for position, entry in enumerate(entries):
        if entry.get('deletedAt') or kind and entry['type'] != kind:
            continue
        if any(tag not in entry['tags'] for tag in tags):
            continue
        title = entry['name'].casefold()
        tag_text = ' '.join(entry['tags']).casefold()
        haystack = '\n'.join([entry['id'], *[entry[k] for k in TEXT_FIELDS],
                              tag_text, entry.get('activationOptions', '')]).casefold()
        if not all(word in haystack for word in words):
            continue
        score = sum(4 * (word in title) + 2 * (word in tag_text) for word in words)
        ranked.append((-score, position, entry))
    return [entry for _, _, entry in sorted(ranked, key=lambda row: row[:2])]


def format_text(entries, by_id, detail=False):
    lines = []
    for entry in entries:
        lines.extend([f'## {entry["name"]} [{entry["id"]}]',
                      f'{entry["type"]} · {entry["status"]} · {" / ".join(entry["tags"])}',
                      entry['summary']])
        if entry['type'] == '技能':
            parts = ' + '.join(by_id[x]['name'] for x in entry['mechanismIds']) or '尚未拆解'
            lines.append('组成机制：' + parts)
        if detail:
            fields = [('trigger', '原始触发示例' if entry['type'] == '技能' else '触发条件'),
                      ('effect', '效果'), ('cost', '代价'), ('synergy', '组合思路'),
                      ('risk', '风险'), ('notes', '原型验证'), ('source', '来源')]
            if entry.get('activationOptions'):
                fields.insert(0, ('activationOptions', '可选触发方式'))
            lines.extend(f'{label}：{entry[key] or "未记录"}' for key, label in fields)
            if entry['relations']:
                lines.append('参考或搭配：' + '、'.join(f'{by_id[x]["name"]} [{x}]' for x in entry['relations']))
        lines.append('')
    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--query', default='', help='Whitespace-separated words; all must match.')
    parser.add_argument('--type', dest='kind', choices=('机制', '技能'))
    parser.add_argument('--tag', action='append', default=[], help='Exact tag; repeat for intersection.')
    parser.add_argument('--id', dest='ids', action='append', default=[], help='Exact ID; repeat for multiple entries.')
    parser.add_argument('--limit', type=int, default=8, help='Maximum search matches; does not trim requested IDs.')
    parser.add_argument('--with-components', action='store_true', help='Include each selected skill\'s component mechanisms once.')
    parser.add_argument('--detail', action='store_true', help='Show full design notes in text output.')
    parser.add_argument('--format', choices=('text', 'json'), default='text')
    parser.add_argument('--check', action='store_true', help='Validate library structure and references, then exit.')
    args = parser.parse_args(argv)
    if args.limit < 1:
        parser.error('--limit must be positive.')
    if args.ids and (args.query or args.kind or args.tag):
        parser.error('Use --id separately from --query, --type and --tag.')
    try:
        entries, by_id = load_library()
        if args.check:
            mechanisms = sum(e['type'] == '机制' for e in entries)
            print(f'Validated {len(entries)} entries: {mechanisms} mechanisms, {len(entries)-mechanisms} skills.')
            return 0
        if args.ids:
            missing = [identifier for identifier in args.ids if identifier not in by_id]
            if missing:
                parser.error('Unknown IDs: ' + ', '.join(missing))
            matches = [by_id[identifier] for identifier in dict.fromkeys(args.ids)]
            selected = list(matches)
        else:
            matches = search(entries, args.query, args.kind, args.tag)
            selected = matches[:args.limit]
        base_count = len(selected)
        if args.with_components:
            seen = {entry['id'] for entry in selected}
            for entry in list(selected):
                for identifier in entry['mechanismIds']:
                    if identifier not in seen:
                        selected.append(by_id[identifier])
                        seen.add(identifier)
        if args.format == 'json':
            print(json.dumps({'matched_count': len(matches), 'selected_count': base_count,
                              'returned_count': len(selected), 'entries': selected}, ensure_ascii=False, indent=2))
        elif selected:
            print(f'匹配 {len(matches)} 条；返回 {base_count} 条及 {len(selected)-base_count} 条组成机制。\n')
            print(format_text(selected, by_id, args.detail))
        else:
            print('没有匹配条目。可减少关键词，或按核心效果换词检索。')
        return 0
    except (OSError, ValueError, TypeError) as error:
        print(f'Library error: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    raise SystemExit(main())
