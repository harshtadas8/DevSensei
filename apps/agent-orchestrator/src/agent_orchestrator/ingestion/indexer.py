import chromadb
from chromadb.config import Settings
from .chunker import chunk_python_file
import os
import hashlib
from urllib.parse import urlparse
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

# Connect to ChromaDB in Embedded Mode (No separate server needed)
client = chromadb.PersistentClient(path="./chroma_data", settings=Settings(allow_reset=True))

def get_or_create_collection(name="devsensei_codebase"):
    return client.get_or_create_collection(name=name)

def index_repository(repo_path: str):
    # Clear the old brain before analyzing a new PR
    try:
        client.delete_collection("devsensei_codebase")
    except Exception:
        pass
        
    collection = get_or_create_collection()
    
    documents = []
    metadatas = []
    ids = []
    
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', '__pycache__', '.venv']]
        for file in files:
            file_path = os.path.join(root, file)
            if file.endswith('.py'):
                try:
                    chunks = chunk_python_file(file_path)
                    for chunk in chunks:
                        doc_id = hashlib.md5(f"{file_path}_{chunk['name']}_{chunk['start_line']}".encode()).hexdigest()
                        documents.append(chunk['content'])
                        metadatas.append({
                            "file_path": chunk['file_path'],
                            "type": chunk['type'],
                            "name": chunk['name'],
                            "start_line": chunk['start_line'],
                            "end_line": chunk['end_line']
                        })
                        ids.append(doc_id)
                except Exception as e:
                    print(f"Failed to process python {file_path}: {e}")
            elif file.endswith(('.js', '.jsx', '.ts', '.tsx', '.html', '.css', '.md')):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        code = f.read()
                    if code.strip():
                        doc_id = hashlib.md5(f"{file_path}_entire_file".encode()).hexdigest()
                        documents.append(code[:4000]) # chunk size limit
                        metadatas.append({
                            "file_path": file_path,
                            "type": "file",
                            "name": file,
                            "start_line": 1,
                            "end_line": len(code.split('\n'))
                        })
                        ids.append(doc_id)
                except Exception as e:
                    print(f"Failed to process {file_path}: {e}")

    if documents:
        print(f"Adding {len(documents)} chunks to ChromaDB...")
        # Chroma API add supports batching but we keep it simple for now
        batch_size = 100
        for i in range(0, len(documents), batch_size):
            collection.upsert(
                documents=documents[i:i+batch_size],
                metadatas=metadatas[i:i+batch_size],
                ids=ids[i:i+batch_size]
            )
        print("Indexing complete!")
        return len(documents)
    else:
        print("No supported code files found to index.")
        return 0

def retrieve_context(query: str, n_results: int = 5):
    collection = get_or_create_collection()
    try:
        results = collection.query(
            query_texts=[query],
            n_results=n_results
        )
        context_chunks = []
        if results and results['documents'] and results['documents'][0]:
            for doc, meta in zip(results['documents'][0], results['metadatas'][0]):
                context_chunks.append(f"File: {meta['file_path']} ({meta['type']} {meta['name']})\n{doc}")
        return "\n\n---\n\n".join(context_chunks)
    except Exception as e:
        print(f"Chroma retrieval failed: {e}")
        return ""
