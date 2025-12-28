# Cline Core

A python library to run cline core

## Installation

Install Cline CLI which includes Cline Core. For more info visit: https://cline.bot/cline-cli

**Global Installation (default):**
```bash
npm install -g cline@1.0.8
```

**Local Installation (recommended):**
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

#### Local Installation Support

The library supports finding `cline-core.js` in multiple locations, in order of priority:

1. **Keyword argument**: Pass `cline_path` to `with_available_ports()`
   ```python
   with ClineInstance.with_available_ports(cline_path="./node_modules/cline/cline-core.js") as instance:
       # Use instance
   ```

2. **Environment variable**: Set `CLINE_CORE_PATH` environment variable
   ```bash
   export CLINE_CORE_PATH="./node_modules/cline/cline-core.js"
   ```

3. **PATH search**: If `cline` executable is found in PATH, searches for `cline-core.js` relative to it

4. **Global npm fallback**: Searches global node_modules (original behavior)

This allows you to install Cline CLI locally in your project directory instead of globally.

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