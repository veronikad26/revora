import re
import pathlib

ROOTS = ["app", "evaluation", "dashboard"]

prefix_re = re.compile(
    r'\A((?:[ \t]*"""[\s\S]*?"""[ \t]*\r?\n)+)(?=[ \t]*from __future__ import annotations)'
)
docstring_re = re.compile(r'"""[\s\S]*?"""')

fixed = []
for root_name in ROOTS:
    root = pathlib.Path(root_name)
    if not root.exists():
        continue
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        m = prefix_re.match(text)
        if not m:
            continue
        docstrings = docstring_re.findall(m.group(1))
        if len(docstrings) <= 1:
            continue  # already fine, only one docstring
        last = docstrings[-1]  # keep the real implementation docstring
        new_text = last + "\n" + text[m.end():]
        path.write_text(new_text, encoding="utf-8")
        fixed.append(str(path))

print(f"Fixed {len(fixed)} files:")
for f in fixed:
    print(" -", f)