"""Build the ChromaDB index from knowledge_base/*.md. Run again after any edit to the .md files."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import shutil
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from lra.rag.kb_utils import load_chunks

DB_DIR = "./chroma_db"

print("1. Loading embedding model (BAAI/bge-small-en-v1.5)...")
embeddings = HuggingFaceEmbeddings(
    model_name="BAAI/bge-small-en-v1.5",
    model_kwargs={"device": "cpu"},
    encode_kwargs={"normalize_embeddings": True},
)

print("2. Reading and chunking knowledge_base/ ...")
chunks = load_chunks()
parents = {c.metadata["parent_id"] for c in chunks}
print(f"   {len(parents)} sections -> {len(chunks)} child chunks")

print("3. Rebuilding ChromaDB (old index deleted so nothing is duplicated)...")
shutil.rmtree(DB_DIR, ignore_errors=True)
Chroma.from_documents(documents=chunks, embedding=embeddings, persist_directory=DB_DIR)
print("Done. Index saved to", DB_DIR)
