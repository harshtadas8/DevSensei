import os
import tree_sitter_python as tspython
from tree_sitter import Language, Parser

def get_python_parser():
    PY_LANGUAGE = Language(tspython.language())
    parser = Parser(PY_LANGUAGE)
    return parser

def chunk_python_file(file_path: str):
    """
    Parses a python file and returns chunks based on functions and classes.
    Returns a list of dicts: [{'type': 'function'|'class', 'name': 'foo', 'content': '...', 'start_line': 1, 'end_line': 10}]
    """
    with open(file_path, "r", encoding="utf-8") as f:
        code = f.read()
    
    parser = get_python_parser()
    tree = parser.parse(bytes(code, "utf8"))
    
    chunks = []
    
    # Simple traversal to find top-level functions and classes
    def traverse(node):
        if node.type in ['function_definition', 'class_definition']:
            name_node = next((n for n in node.named_children if n.type == 'identifier'), None)
            name = name_node.text.decode('utf8') if name_node else "anonymous"
            
            start_line = node.start_point[0]
            end_line = node.end_point[0]
            
            content = code[node.start_byte:node.end_byte]
            
            chunks.append({
                "type": node.type,
                "name": name,
                "content": content,
                "start_line": start_line + 1,
                "end_line": end_line + 1,
                "file_path": file_path
            })
            # Don't recurse into classes/functions to keep chunks top-level
            return
            
        for child in node.children:
            traverse(child)

    traverse(tree.root_node)
    
    # If no functions/classes found, treat the whole file as a chunk
    if not chunks and code.strip():
        chunks.append({
            "type": "file",
            "name": os.path.basename(file_path),
            "content": code,
            "start_line": 1,
            "end_line": len(code.split('\n')),
            "file_path": file_path
        })
        
    return chunks
