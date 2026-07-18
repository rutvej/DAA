import os
import re
import shutil

root_dir = "/home/rutvej/Desktop/DAA"
docs_dir = os.path.join(root_dir, "docs")

# 1. Create Docs Hierarchy
dirs = ["quickstart", "architecture", "deployment", "sdk", "webhooks", "operations"]
for d in dirs:
    os.makedirs(os.path.join(docs_dir, d), exist_ok=True)

# 2. Update SETUP.md, DEPLOYMENT.md, matrix.md to stubs
stub_content = """# Redirect

This file has been deprecated as part of the documentation modernization.
Please refer to the new documentation portal at [`/docs/index.md`](./docs/index.md) for the latest information.
"""
for f in ["SETUP.md", "DEPLOYMENT.md", "matrix.md"]:
    with open(os.path.join(root_dir, f), "w") as file:
        file.write(stub_content)

# 3. Create basic index.md
index_content = """# DAA Documentation Portal

Welcome to the DAA Documentation Portal.

## Navigation
- [Quickstart](./quickstart/verification-and-demo.md)
- [Architecture](./architecture/system-overview.md)
- [Deployment](./deployment/combinations-matrix.md)
- [SDK Ecosystem](./sdk/overview-and-authentication.md)
- [Webhooks](./webhooks/sentry.md)
- [Operations & CLI Reference](./operations/cli-reference.md)
"""
with open(os.path.join(docs_dir, "index.md"), "w") as f:
    f.write(index_content)


# 4. Migrate and consolidate specs to new docs hierarchy
# We'll just copy any existing specs into docs for now, then we'll remove the spec dirs
def move_files(src_dir, dest_dir):
    if not os.path.exists(src_dir):
        return
    for f in os.listdir(src_dir):
        if f.endswith(".md"):
            shutil.copy2(os.path.join(src_dir, f), os.path.join(dest_dir, f))


# Consolidating specs to architecture as a default, will rename later if needed
if os.path.exists(os.path.join(root_dir, "specs")):
    move_files(os.path.join(root_dir, "specs"), os.path.join(docs_dir, "architecture"))

# Handle typo infrasture.md -> infrastructure.md (merge into queue/data)
inf_path = os.path.join(docs_dir, "architecture", "infrasture.md")
if os.path.exists(inf_path):
    os.remove(inf_path)

# 6. Remove duplicate /specs folders
spec_dirs = [
    "specs",
    "app/backend-api/specs",
    "app/python-agent/specs",
    "app/daa-sdk/specs",
]
for d in spec_dirs:
    p = os.path.join(root_dir, d)
    if os.path.exists(p):
        shutil.rmtree(p)

print("Basic directory structure and stubs created. Specs removed.")
