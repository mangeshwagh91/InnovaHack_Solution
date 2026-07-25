import os

def concat_files(startpath, outfile):
    with open(outfile, 'w', encoding='utf-8') as out:
        for root, dirs, files in os.walk(startpath):
            dirs[:] = [d for d in dirs if d not in ('.git', 'node_modules', 'venv', '.venv', '__pycache__', 'chroma_db', 'uploads')]
            for file in files:
                if file.endswith(('.py', '.jsx', '.js', '.md', '.html', '.css', '.json', '.txt', '.env')):
                    # Skip large files like package-lock.json
                    if file == 'package-lock.json': continue
                    filepath = os.path.join(root, file)
                    rel_path = os.path.relpath(filepath, startpath)
                    out.write(f"\n\n{'='*80}\n")
                    out.write(f"FILE: {rel_path}\n")
                    out.write(f"{'='*80}\n\n")
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            out.write(f.read())
                    except Exception as e:
                        out.write(f"Error reading file: {e}\n")

concat_files('c:/Users/manas/OneDrive/Desktop/MY_version_ET', 'c:/Users/manas/OneDrive/Desktop/MY_version_ET/all_code.txt')
print("Code concatenated.")
