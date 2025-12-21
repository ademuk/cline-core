# Cline Core

A python library to run cline core

## Installation

Install Cline CLI which includes Cline Core. For more info visit: https://cline.bot/cline-cli
```bash
RUN npm install -g cline@1.0.8
```

Install this library

```bash
pip install cline_core
```

## Usage

### Basic Cline Instance Management

```python
from cline_core import ClineInstance

with ClineInstance.with_available_ports() as instance:
    print(f"Instance started: {instance.address}")
    # Use the instance
```

### Examples

See `examples/example.py` for a complete example of creating and monitoring tasks.

## API Reference

### ClineInstance

`ClineInstance` class for managing Cline Core processes.

#### Methods

- **start()**: Launches cline-host and cline-core.js processes, waits for instance lock
- **stop()**: Terminates the processes
- **wait_for_instance(timeout=30)**: Waits for instance lock in database
- **is_running()**: Checks if processes are still running
- **with_available_ports(cwd, config_path=None)**: Factory method for automatic port allocation

Supports context manager protocol for automatic cleanup.

### Protocol Buffer Files

The library includes gRPC protocol buffer definitions and generated Python files for communicating with Cline's gRPC services. These files are located in `src/cline/proto/` and include:

- Task management (`task_pb2.py`)
- State management (`state_pb2.py`)
- Common types (`common_pb2.py`)
- And more...

Protocol buffer files are automatically generated during the build process using `uv build`. The generated files are included in the package distribution but ignored in version control.

To manually regenerate these files during development:

```bash
uv run build.py
```

## Development

This project uses uv for package management and development.

```bash
# Install dependencies
uv sync --dev

# Run tests
uv run pytest

# Semantic release (handled by CI)
```

- Automatic versioning with python-semantic-release
- CI/CD with GitHub Actions
