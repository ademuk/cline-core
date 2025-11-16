"""
Custom build backend that generates protobuf files before building.

This extends uv_build to automatically generate Python protobuf files from .proto definitions.
"""
import subprocess
import sys
from pathlib import Path

try:
    from uv_build import build_uv
except ImportError:
    # Fallback if uv_build is not available
    import setuptools.build_meta as build_uv


def generate_proto_files():
    """Generate Python protobuf files from .proto definitions."""
    project_root = Path(__file__).parent
    proto_dir = project_root / "src" / "cline_core" / "proto"
    proto_files_dir = proto_dir / "cline"

    # Ensure output directory exists
    proto_files_dir.mkdir(parents=True, exist_ok=True)

    # Find all .proto files
    proto_files = list(proto_files_dir.glob("*.proto"))
    if not proto_files:
        print("Warning: No .proto files found - skipping generation", file=sys.stderr)
        return

    print(f"Generating code from {len(proto_files)} proto files...")

    # Generate protobuf files
    try:
        cmd = [
            sys.executable, "-m", "grpc_tools.protoc",
            "--proto_path", str(proto_dir),
            "--python_out", str(proto_dir),
            "--grpc_python_out", str(proto_dir),
        ] + [str(f) for f in proto_files]

        result = subprocess.run(cmd, capture_output=True, text=True, cwd=project_root)

        if result.returncode != 0:
            print("Error generating protobuf files:", file=sys.stderr)
            print("STDOUT:", result.stdout, file=sys.stderr)
            print("STDERR:", result.stderr, file=sys.stderr)
            raise RuntimeError("Protobuf generation failed")

        # Fix import paths in generated files
        pb2_files = list(proto_dir.glob("cline/*_pb2.py"))
        pb2_grpc_files = list(proto_dir.glob("cline/*_pb2_grpc.py"))

        all_pb_files = pb2_files + pb2_grpc_files

        if all_pb_files:
            # Replace incorrect absolute imports with relative imports
            for pb_file in all_pb_files:
                content = pb_file.read_text()
                fixed_content = content.replace("from cline import ", "from . import ")
                pb_file.write_text(fixed_content)

        print(f"Successfully generated {len(all_pb_files)} protobuf files")

    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Error running protoc: {e}") from e
    except Exception as e:
        raise RuntimeError(f"Unexpected error during proto generation: {e}") from e


# Monkey patch the build_uv functions to run proto generation first
try:
    _original_prepare_metadata_for_build_wheel = build_uv.prepare_metadata_for_build_wheel
    _original_build_wheel = build_uv.build_wheel
    _original_build_sdist = build_uv.build_sdist
    _original_prepare_metadata_for_build_sdist = build_uv.prepare_metadata_for_build_sdist

    def prepare_metadata_for_build_wheel(*args, **kwargs):
        generate_proto_files()
        return _original_prepare_metadata_for_build_wheel(*args, **kwargs)

    def build_wheel(*args, **kwargs):
        generate_proto_files()
        return _original_build_wheel(*args, **kwargs)

    def build_sdist(*args, **kwargs):
        generate_proto_files()
        return _original_build_sdist(*args, **kwargs)

    def prepare_metadata_for_build_sdist(*args, **kwargs):
        generate_proto_files()
        return _original_prepare_metadata_for_build_sdist(*args, **kwargs)

    # Update the build_uv module with our wrapped functions
    build_uv.prepare_metadata_for_build_wheel = prepare_metadata_for_build_wheel
    build_uv.build_wheel = build_wheel
    build_uv.build_sdist = build_sdist
    build_uv.prepare_metadata_for_build_sdist = prepare_metadata_for_build_sdist

except AttributeError:
    # uv_build might not have all these methods, skip patching
    pass


if __name__ == "__main__":
    # Allow running this script directly
    generate_proto_files()
