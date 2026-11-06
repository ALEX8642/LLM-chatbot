import os

# Set before torch loads. On a dev run the slowest retrieval fell from 57 s to 14 s on a
# 16 GB GPU, and the memory spilled to system RAM from 3.5 GB to under 2 GB.
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
