"""
BibTeX parser for Better BibTeX exports (e.g. My Library.bib).

Handles three things naive regex misses:
1. Brace-balanced values: title = {{Foo} {Bar}} -- nested braces
2. Bare values: year = 2024 (no braces)
3. Author lists: author = {Name1 and Name2 and Name3} -> [{family, given}, ...]

Returns dict of citekey -> entry fields.

Usage in execute_code (each call is fresh process):
    from parse_bib import parse_bib
    with open('/home/luosg/Work/luosg/Zotero/My Library.bib') as f:
        entries = parse_bib(f.read())
    e = entries['adamsGeneticDeterminantsMicronucleus2024']
    print(e['title'], e['year'], len(e['author']))
"""

import re


def parse_bib(text: str) -> dict:
    entries = {}
    for m in re.finditer(r'@(\w+)\s*\{\s*([^,\s]+)\s*,', text):
        etype = m.group(1).lower()
        key = m.group(2).strip()
        start = m.end()
        depth = 1
        i = start
        while i < len(text) and depth > 0:
            if text[i] == '{':
                depth += 1
            elif text[i] == '}':
                depth -= 1
            i += 1
        body = text[start:i - 1]

        fields = {'entrytype': etype}
        j = 0
        while j < len(body):
            while j < len(body) and body[j] in ' \t\n\r,':
                j += 1
            if j >= len(body):
                break
            m2 = re.match(r'(\w+)\s*=\s*', body[j:])
            if not m2:
                j += 1
                continue
            name = m2.group(1).lower()
            j += m2.end()
            if j < len(body) and body[j] == '{':
                depth2 = 1
                k = j + 1
                while k < len(body) and depth2 > 0:
                    if body[k] == '{':
                        depth2 += 1
                    elif body[k] == '}':
                        depth2 -= 1
                    k += 1
                val = body[j + 1:k - 1]
                j = k
            elif j < len(body) and body[j] == '"':
                k = j + 1
                while k < len(body) and body[k] != '"':
                    if body[k] == '\\':
                        k += 2
                        continue
                    k += 1
                val = body[j + 1:k]
                j = k + 1
            else:
                k = j
                while k < len(body) and body[k] not in ',\n':
                    k += 1
                val = body[j:k].strip()
                j = k

            if name == 'author':
                authors = []
                for a in val.split(' and '):
                    a = a.strip()
                    if not a:
                        continue
                    if ',' in a:
                        parts = a.split(',', 1)
                        fam, given = parts[0].strip(), parts[1].strip()
                    else:
                        parts = a.split()
                        fam = parts[-1]
                        given = ' '.join(parts[:-1])
                    authors.append({'family': fam, 'given': given})
                fields['author'] = authors
            else:
                fields[name] = val.strip()
        entries[key] = fields
    return entries


def decode_latex(s: str) -> str:
    """Decode Better BibTeX LaTeX escapes used in author names.
    e.g. Olvera-Le{\\'o}n -> Olvera-León
    """
    if not s:
        return s
    # Common escapes
    repl = {
        "\\'o": 'ó', "\\'a": 'á', "\\'e": 'é', "\\'i": 'í', "\\'u": 'ú',
        "\\'O": 'Ó', "\\'A": 'Á', "\\'E": 'É', "\\'I": 'Í', "\\'U": 'Ú',
        "\\'n": 'ń', "\\'N": 'Ń',
        '\\"o': 'ö', '\\"a': 'ä', '\\"u': 'ü',
        '\\~n': 'ñ', '\\~N': 'Ñ',
        '\\c{c}': 'ç', '\\c{C}': 'Ç',
        '\\&': '&',
    }
    for k, v in repl.items():
        s = s.replace(k, v)
    return s


def strip_braces(s: str) -> str:
    """Remove {...} wrapper brackets that Better BibTeX uses to preserve casing."""
    if not s:
        return s
    return s.replace('{', '').replace('}', '')
