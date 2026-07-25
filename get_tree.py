import os
import json

def get_tree(startpath):
    tree = {}
    for root, dirs, files in os.walk(startpath):
        # Exclude common directories to speed up and clean output
        dirs[:] = [d for d in dirs if d not in ('.git', 'node_modules', 'venv', '.venv', '__pycache__', 'chroma_db', 'uploads')]
        
        rel_path = os.path.relpath(root, startpath)
        if rel_path == '.':
            rel_path = ''
            
        tree[rel_path] = {
            'dirs': dirs,
            'files': files
        }
    return tree

tree = get_tree('c:/Users/manas/OneDrive/Desktop/MY_version_ET')
with open('c:/Users/manas/OneDrive/Desktop/MY_version_ET/tree.json', 'w') as f:
    json.dump(tree, f, indent=2)
print("Tree generated.")
