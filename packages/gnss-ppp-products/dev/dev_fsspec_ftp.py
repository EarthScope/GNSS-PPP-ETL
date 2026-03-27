"""Quick test: create an fsspec FTP filesystem for igs.gnsswhu.cn."""

import fsspec

url = (
    "ftp://igs.gnsswhu.cn/pub/whu/phasebias/2025/clock/"
)
print(f"Attempting to open: {url}")

try:
    fs, path = fsspec.core.url_to_fs(url)
    print(f"Filesystem type: {type(fs).__name__}")
    print(f"Parsed path: {path}")
    print(f"Protocol: {fs.protocol}")
    remote_file = path.rstrip("/") + "/WUM0MGXRAP_20253070000_01D_30S_CLK.CLK.gz"
    target_dir = "/Volumes/DunbarSSD/Project/SeafloorGeodesy/GNSS-PPP/test_downloads"
    import os
    os.makedirs(target_dir, exist_ok=True)
    local_path = os.path.join(target_dir, "WUM0MGXRAP_20253070000_01D_30S_CLK.CLK.gz")
    output = fs.get(remote_file, local_path)
    print(f"Output: {output}")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
