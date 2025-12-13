#!/usr/bin/env python3
"""Build script for generating gRPC stubs and fixing import paths."""

import glob
import os
import subprocess
import sys
from typing import List


def run_command(command: List[str], cwd: str = None) -> int:
    """Run a command and return the exit code."""
    print(f"Running: {' '.join(command)}")
    result = subprocess.run(command, cwd=cwd or os.getcwd())
    return result.returncode


def generate_grpc_stubs():
    """Generate gRPC Python stubs from proto files."""
    proto_path = "./src/cline_core/proto"
    output_path = "./src/cline_core/proto"

    # Find all proto files
    proto_files = glob.glob("src/cline_core/proto/**/*.proto", recursive=True)

    if not proto_files:
        print("No proto files found!")
        return False

    command = [
        sys.executable, "-m", "grpc_tools.protoc",
        "--proto_path=" + proto_path,
        "--python_out=" + output_path,
        "--grpc_python_out=" + output_path,
    ] + proto_files

    return run_command(command) == 0


def fix_grpc_imports():
    """Fix import paths in generated gRPC files."""
    import glob
    import re

    # Find all _pb2.py and _pb2_grpc.py files
    pb2_files = glob.glob("src/cline_core/proto/**/*_pb2*.py", recursive=True)

    for pb2_file in pb2_files:
        try:
            with open(pb2_file, 'r') as f:
                content = f.read()

            # Replace the imports
            old_content = content
            content = re.sub(
                r'from cline import (\w+)_pb2 as',
                r'from cline_core.proto.cline import \1_pb2 as',
                content
            )
            content = re.sub(
                r'from host import (\w+)_pb2 as',
                r'from cline_core.proto.host import \1_pb2 as',
                content
            )

            # Only write if changed
            if content != old_content:
                with open(pb2_file, 'w') as f:
                    f.write(content)

        except Exception as e:
            print(f"Error processing {pb2_file}: {e}")
            return False

    return True


def main():
    """Main build function."""
    print("Building gRPC stubs...")

    if not generate_grpc_stubs():
        print("Failed to generate gRPC stubs")
        return 1

    print("Fixing gRPC import paths...")

    if not fix_grpc_imports():
        print("Failed to fix gRPC import paths")
        return 1

    print("Build completed successfully!")
    return 0


if __name__ == "__main__":
    sys.exit(main())