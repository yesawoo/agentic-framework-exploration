"""Shared parsing for the speckit workflow tooling (read-only; stdlib only)."""
import math
import re
from pathlib import Path

TASK_RE = re.compile(r"^- \[[ xX]\] (T\d{3}a?|@@[\w-]+@@)(?=\s)\s*(.*)$")
PHASE_RE = re.compile(r"^## Phase (\d+): (.*)$")
TICK_RE = re.compile(r"`([^`\n]+)`")
FILE_EXT = (".py", ".ts", ".md", ".yaml", ".yml", ".sql", ".json", ".tf", ".js", ".toml", ".lock")
BARE_FILES = {"justfile", "compose.yaml", "Dockerfile", "README.md", "CLAUDE.md"}
STOP = set(
    "a an and are as at be by for from has have in into is it its of on or that the this to with without "
    "each every all any per not no only also than then when while must should may can will use used using "
    "implement write add create task tasks per via one two three four both other same new more less".split()
)


def read(path):
    return Path(path).read_text(encoding="utf-8")


def looks_like_path(tok):
    t = tok.strip()
    if " " in t or len(t) < 3:
        return False
    if t in BARE_FILES:
        return True
    if "/" in t and re.match(r"^[\w.\-/${}<>*@]+$", t):
        return True
    return t.endswith(FILE_EXT) and re.match(r"^[\w.\-${}<>*@]+$", t) is not None


def is_concrete_path(p):
    return not any(c in p for c in "<>*{}$@") and not p.endswith("/")


def parse_tasks(feature_dir):
    """Return (tasks, phases). tasks: list of dicts in file order."""
    lines = read(Path(feature_dir) / "tasks.md").split("\n")
    phases, tasks = [], []
    cur = None
    for i, line in enumerate(lines, 1):
        m = PHASE_RE.match(line)
        if m:
            title = m.group(2)
            sm = re.search(r"User Story (\d+)", title)
            cur = {
                "number": int(m.group(1)),
                "title": title,
                "story": int(sm.group(1)) if sm else None,
                "line": i,
                "tasks": [],
            }
            phases.append(cur)
            continue
        m = TASK_RE.match(line)
        if m:
            text = m.group(2)
            head = re.match(r"^((?:\[[^\]]+\]\s*)+)", text)
            labels = re.findall(r"\[([^\]]+)\]", head.group(1)) if head else []
            paths = []
            for tok in TICK_RE.findall(text):
                if looks_like_path(tok):
                    paths.append(tok.strip())
            t = {
                "id": m.group(1),
                "line": i,
                "text": text,
                "phase": cur["number"] if cur else None,
                "parallel": "P" in labels,
                "story": next((int(x[2:]) for x in labels if re.match(r"US\d+$", x)), None),
                "paths": paths,
            }
            tasks.append(t)
            if cur:
                cur["tasks"].append(t["id"])
    return tasks, phases


def parse_requirements(feature_dir):
    """FR-### / SC-### bullet lines from spec.md -> {id: text}."""
    reqs = {}
    for line in read(Path(feature_dir) / "spec.md").split("\n"):
        m = re.match(r"^- \*\*((?:FR|SC)-\d{3})\*\*:\s*(.*)$", line)
        if m:
            reqs[m.group(1)] = m.group(2)
    return reqs


def parse_stories(feature_dir):
    """{story number: section text} from spec.md."""
    lines = read(Path(feature_dir) / "spec.md").split("\n")
    out, cur, buf = {}, None, []
    for line in lines:
        m = re.match(r"^### User Story (\d+) - ", line)
        if m or re.match(r"^##? ", line) or re.match(r"^### (Edge Cases|Functional|Key Entities|Measurable)", line):
            if cur is not None:
                out[cur] = "\n".join(buf).strip()
            cur = int(m.group(1)) if m else None
            buf = [line] if m else []
        elif cur is not None:
            buf.append(line)
    if cur is not None:
        out[cur] = "\n".join(buf).strip()
    return out


def sections(text, heading_re):
    """Split markdown into {key: section text} where heading_re has one capture group for the key."""
    out, key, buf = {}, None, []
    for line in text.split("\n"):
        m = re.match(heading_re, line)
        if m or re.match(r"^##? ", line):
            if key is not None:
                out.setdefault(key, "\n".join(buf).strip())
            key = m.group(1) if m else None
            buf = [line] if m else []
        elif key is not None:
            buf.append(line)
    if key is not None:
        out.setdefault(key, "\n".join(buf).strip())
    return out


def tokens(text):
    words = []
    for w in re.findall(r"[A-Za-z][A-Za-z0-9_]*", text):
        for part in re.split(r"_+", w):
            for sub in re.findall(r"[A-Z]?[a-z0-9]+|[A-Z]+(?![a-z])", part):
                s = sub.lower()
                if len(s) > 2 and s not in STOP:
                    words.append(s)
    return words


class BM25:
    def __init__(self, docs, k1=1.5, b=0.75):
        self.k1, self.b = k1, b
        self.docs = [tokens(d) for d in docs]
        self.avg = (sum(len(d) for d in self.docs) / len(self.docs)) if self.docs else 0
        df = {}
        for d in self.docs:
            for w in set(d):
                df[w] = df.get(w, 0) + 1
        n = len(self.docs)
        self.idf = {w: math.log(1 + (n - c + 0.5) / (c + 0.5)) for w, c in df.items()}

    def score(self, query, idx):
        d = self.docs[idx]
        if not d:
            return 0.0
        tf = {}
        for w in d:
            tf[w] = tf.get(w, 0) + 1
        s = 0.0
        for w in set(tokens(query)):
            if w in tf:
                f = tf[w]
                s += self.idf.get(w, 0) * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * len(d) / (self.avg or 1)))
        return s

    def top(self, query, n=3):
        scored = [(self.score(query, i), i) for i in range(len(self.docs))]
        scored.sort(reverse=True)
        return [(i, round(s, 2)) for s, i in scored[:n] if s > 0]
