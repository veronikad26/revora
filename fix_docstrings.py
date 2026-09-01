import re
import pathlib

ROOTS = ["app", "evaluation", "dashboard"]

block_re = re.compile(r'[ \t]*"""[\s\S]*?"""[ \t]*\r?\n')
blank_re = re.compile(r'[ \t]*\r?\n')

def fix_file(path):
    text = path.read_text(encoding="utf-8")
    pos = 0
    blocks = []
    while True:
        while True:
            bm = blank_re.match(text, pos)
            if not bm:
                break
            pos = bm.end()
        m = block_re.match(text, pos)
        if not m:
            break
        blocks.append(m)
        pos = m.end()

    if len(blocks) <= 1:
        return False

    last = blocks[-1]
    new_text = last.group(0) + text[last.end():]
    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
        return True
    return False

fixed = []
for root_name in ROOTS:
    root = pathlib.Path(root_name)
    if not root.exists():
        continue
    for path in root.rglob("*.py"):
        if fix_file(path):
            fixed.append(str(path))

print(f"Fixed {len(fixed)} files:")
for f in fixed:
    print(" -", f)