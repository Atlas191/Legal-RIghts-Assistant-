"""Shared helpers: load the knowledge_base/*.md files into parent-child chunks."""
import os
import re
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

KB_DIR = "knowledge_base"
CHILD_SIZE = 700      # characters per child chunk (bge-small reads ~512 tokens max)
CHILD_OVERLAP = 100


def parse_front_matter(text):
    """Return (metadata dict, text without the --- block)."""
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    meta = {}
    if m:
        for line in m.group(1).splitlines():
            if ":" in line and not line.startswith(" "):
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
        text = text[m.end():]
    return meta, text


_META_KEYS = frozenset({
    "section", "sections", "topic", "formerly_ipc", "keywords",
    "source", "status", "act_section_quoted", "form",
})


def parse_meta_lines(body):
    """Read the leading '- key: value | key: value' lines. Return (meta, remaining body)."""
    meta, lines = {}, body.splitlines()
    i = 0
    while i < len(lines) and lines[i].startswith("- ") and ":" in lines[i]:
        pairs = {}
        for piece in lines[i][2:].split(" | "):
            k, _, v = piece.partition(":")
            pairs[k.strip()] = v.strip()
        accepted = {k: v for k, v in pairs.items() if k in _META_KEYS}
        if not accepted:
            break                       # first line with no recognised keys → body starts
        meta.update(accepted)
        i += 1
    return meta, "\n".join(lines[i:]).strip()


def load_chunks(kb_dir=KB_DIR):
    """One '## ' block = one parent. Each parent is split into small child chunks."""
    splitter = RecursiveCharacterTextSplitter(chunk_size=CHILD_SIZE, chunk_overlap=CHILD_OVERLAP)
    children = []
    for fname in sorted(os.listdir(kb_dir)):
        if not fname.endswith(".md"):
            continue
        with open(os.path.join(kb_dir, fname), encoding="utf-8") as f:
            fm, text = parse_front_matter(f.read())
        doc_id = fm.get("doc_id", fname[:-3])
        act = fm.get("act") or fm.get("org") or doc_id
        parts = re.split(r"^## ", text, flags=re.M)[1:]
        for p_idx, part in enumerate(parts):
            heading, _, body = part.partition("\n")
            heading = heading.strip()
            body = re.sub(r"^# .*$", "", body, flags=re.M)      # drop H1 group titles
            sec_meta, body = parse_meta_lines(body.strip())
            keywords = sec_meta.get("keywords", "")
            section = sec_meta.get("section") or sec_meta.get("sections") or heading.split(" — ")[0]
            parent_id = f"{doc_id}:{p_idx}"
            parent_text = f"{heading}\n{body}"
            split_pieces = splitter.split_text(body)
            if not split_pieces:
                split_pieces = [body] if body.strip() else [heading]
            for c_idx, piece in enumerate(split_pieces):
                # Heading + keywords are repeated in every child so it is searchable on its own.
                content = f"{heading}\nKeywords: {keywords}\n{piece}"
                children.append(Document(page_content=content, metadata={
                    "child_id": f"{parent_id}:{c_idx}",
                    "parent_id": parent_id,
                    "parent_text": parent_text,
                    "doc_id": doc_id,
                    "act": act,
                    "section": section,
                    "heading": heading,
                    "topic": sec_meta.get("topic", ""),
                    "formerly_ipc": sec_meta.get("formerly_ipc", ""),
                    "source_file": fm.get("source_file", fname),
                }))
    return children


STOPWORDS = set("a an the and or of to in on at by for from with is are was were be been it its my me i you he she they we our your his her their this that these those as but if so not no do does did have has had after before about into over than then there here can will would should could may might just also very keeps keep guy what how who which when where why tell please help need want get know give show".split())
# Domain stopwords: terms that appear in nearly every chunk of this Indian-law corpus
# and carry no discriminative signal for BM25 retrieval.
STOPWORDS |= {"india", "indian", "woman", "women", "section", "act", "shall", "under", "provision", "provisions", "provided", "law", "rights", "may"}


def tokenize(text):
    """Lowercase word tokens with common filler words removed (used for BM25)."""
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOPWORDS]