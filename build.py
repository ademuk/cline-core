from hatchling.builders.hooks.plugin.interface import BuildHookInterface
import subprocess
from pathlib import Path

class CustomBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        proto_dir = Path("src/cline_core/proto")
        proto_cline_dir = proto_dir / "cline"
        out_dir = Path("src/cline_core/proto")
        out_dir.mkdir(parents=True, exist_ok=True)

        subprocess.check_call([
            "python", "-m", "grpc_tools.protoc",
            f"--proto_path={proto_dir}",
            f"--python_out={out_dir}",
            f"--grpc_python_out={out_dir}",
            *[str(p) for p in proto_cline_dir.glob("*.proto")]
        ])
