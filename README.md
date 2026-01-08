# Cline Core

A python library to run cline core

## Installation

Install Cline CLI which includes Cline Core. For more info visit: https://cline.bot/cline-cli

**Global Installation (recommended for most users):**
```bash
npm install -g cline@1.0.8
```

**Local Installation (project-specific):**
```bash
npm install cline@1.0.8
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
- **with_available_ports(cwd=None, config_path=None, cline_path=None)**: Factory method for automatic port allocation

Supports context manager protocol for automatic cleanup.

#### Local Node Package Support

By default, Cline Core looks for `cline-core.js` in globally installed npm packages. For local installations, you have several options:

1. **Keyword Argument**: Pass `cline_path` to `with_available_ports()`
   ```python
   # Directory containing cline-core.js
   instance = ClineInstance.with_available_ports(cline_path="/path/to/node_modules/cline")

   # Direct path to cline-core.js
   instance = ClineInstance.with_available_ports(cline_path="/path/to/cline-core.js")

   # Path to cline executable (will find cline-core.js in same directory)
   instance = ClineInstance.with_available_ports(cline_path="/path/to/cline")
   ```

2. **Environment Variable**: Set `CLINE_PATH` environment variable
   ```bash
   export CLINE_PATH="/path/to/node_modules/cline"
   ```
   Then use normally:
   ```python
   instance = ClineInstance.with_available_ports()
   ```

3. **PATH Search**: If `cline` executable is in your PATH, it will automatically find `cline-core.js` in the same directory
   ```bash
   export PATH="/path/to/cline/dir:$PATH"
   ```
   Then use normally:
   ```python
   instance = ClineInstance.with_available_ports()
   ```

The search order is: keyword argument → environment variable → PATH search → global npm install (fallback).

## Development

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