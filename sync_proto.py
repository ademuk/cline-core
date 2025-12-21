#!/usr/bin/env python3
"""
Script to sync .proto files from a given directory into ./src/cline_core/proto
Usage: python sync_proto.py <source_directory>
"""

import sys
import shutil
from pathlib import Path


def sync_proto_files(source_dir: str):
    """
    Sync .proto files from source_dir/proto/**/*.proto to ./src/cline_core/proto
    """
    source_path = Path(source_dir)
    if not source_path.exists():
        print(f"Error: Source directory {source_dir} does not exist")
        return False

    proto_source = source_path / "proto"
    if not proto_source.exists():
        print(f"Error: {proto_source} does not exist")
        return False

    dest_root = Path("./src/cline_core/proto")

    # Find all .proto files recursively
    proto_files = list(proto_source.rglob("*.proto"))
    if not proto_files:
        print(f"No .proto files found in {proto_source}")
        return False

    synced_files = 0
    for proto_file in proto_files:
        # Calculate relative path from proto_source
        relative_path = proto_file.relative_to(proto_source)
        dest_file = dest_root / relative_path

        # Create destination directory if it doesn't exist
        dest_file.parent.mkdir(parents=True, exist_ok=True)

        # Copy the file
        shutil.copy2(proto_file, dest_file)
        print(f"Synced: {proto_file} -> {dest_file}")
        synced_files += 1

    print(f"Successfully synced {synced_files} .proto files")
    return True


def main():
    if len(sys.argv) != 2:
        print("Usage: python sync_proto.py <source_directory>")
        sys.exit(1)

    source_dir = sys.argv[1]
    success = sync_proto_files(source_dir)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
