import logging
import os
import socket
import sqlite3
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple


logger = logging.getLogger('cline_agent')


def get_cline_core_path(cline_path: Optional[str] = None) -> str:
    # Option 1: Accept relative path as keyword argument
    if cline_path:
        if os.path.isabs(cline_path):
            # Absolute path provided
            candidate_path = cline_path
        else:
            # Relative path - resolve relative to current working directory
            candidate_path = os.path.join(os.getcwd(), cline_path)

        if os.path.exists(candidate_path):
            logger.info(f"Using provided path: cline-core.js found at {candidate_path}")
            return candidate_path
        else:
            raise FileNotFoundError(f"cline-core.js not found at provided path: {candidate_path}")

    # Option 2: Accept relative path as environment variable
    env_cline_path = os.environ.get('CLINE_CORE_PATH')
    if env_cline_path:
        if os.path.isabs(env_cline_path):
            candidate_path = env_cline_path
        else:
            candidate_path = os.path.join(os.getcwd(), env_cline_path)

        if os.path.exists(candidate_path):
            logger.info(f"Using environment variable CLINE_CORE_PATH: cline-core.js found at {candidate_path}")
            return candidate_path
        else:
            logger.warning(f"CLINE_CORE_PATH environment variable set but file not found: {candidate_path}")

    # Option 3: Search PATH for cline executables
    try:
        cline_executable = subprocess.check_output(['which', 'cline'], text=True).strip()
        if cline_executable:
            # Derive the path to cline-core.js from the cline executable
            cline_dir = os.path.dirname(cline_executable)
            candidate_path = os.path.join(cline_dir, '..', 'lib', 'node_modules', 'cline', 'cline-core.js')
            # Also try relative to the executable directory
            if not os.path.exists(candidate_path):
                candidate_path = os.path.join(cline_dir, 'cline-core.js')

            if os.path.exists(candidate_path):
                logger.info(f"Using PATH search: cline-core.js found at {candidate_path}")
                return candidate_path
            else:
                logger.warning(f"Found cline executable at {cline_executable} but could not locate cline-core.js")
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as e:
        logger.debug(f"Could not find cline in PATH: {e}")

    # Option 4: Fall back to global npm install (original behavior)
    try:
        global_npm_root = subprocess.check_output(['npm', 'root', '-g'], text=True).strip()
        global_cline_core_path = os.path.join(global_npm_root, 'cline', 'cline-core.js')

        logger.info(f"Checking global node_modules path: {global_cline_core_path}")

        if os.path.exists(global_cline_core_path):
            logger.info(f"Using global install: cline-core.js found at {global_cline_core_path}")
            return global_cline_core_path
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as e:
        logger.warning(f"Could not determine global npm root or check global path: {e}")

    raise FileNotFoundError("cline-core.js not found. Make sure cline is installed globally with 'npm install -g cline', or provide a path via the cline_path parameter or CLINE_CORE_PATH environment variable, or ensure 'cline' is in your PATH.")


class InstanceLockNotFoundError(Exception):
    pass


@dataclass
class Instance:
    address: str  # held_by field from database
    lock_target: str
    locked_at: str


def find_available_port_pair() -> Tuple[int, int]:
    host_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    host_socket.bind(('', 0))
    host_port = host_socket.getsockname()[1]
    host_socket.close()

    core_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    core_socket.bind(('', 0))
    core_port = core_socket.getsockname()[1]
    core_socket.close()

    return host_port, core_port


class ClineInstance:
    @classmethod
    def with_available_ports(cls, cwd: Optional[Path] = None, config_path: Optional[Path] = None, cline_path: Optional[str] = None) -> 'ClineInstance':
        if cwd is None:
            cwd = Path.cwd()
        host_port, core_port = find_available_port_pair()
        return cls(cline_host_port=host_port, cline_core_port=core_port, config_path=config_path, cwd=cwd, cline_path=cline_path)

    def __init__(self, cline_host_port: int, cline_core_port: int, config_path: Optional[Path], cwd: Path, cline_path: Optional[str] = None) -> None:
        self.cline_host_port = cline_host_port
        self.cline_core_port = cline_core_port
        self.config_path = config_path if config_path is not None else Path.home() / ".cline"
        self.cwd = cwd
        self.cline_path = cline_path
        self.host_process: Optional[subprocess.Popen[str]] = None
        self.core_process: Optional[subprocess.Popen[str]] = None

    def start(self) -> Instance:
        self.host_process = subprocess.Popen(
            ['cline-host', '--verbose', '--port', str(self.cline_host_port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            cwd=self.cwd
        )

        cline_core_path = get_cline_core_path(self.cline_path)

        real_node_modules = os.path.join(os.path.dirname(cline_core_path), "node_modules")
        fake_node_modules = os.path.join(os.path.dirname(cline_core_path), "fake_node_modules")
        node_path = f"{real_node_modules}{os.pathsep}{fake_node_modules}"

        self.core_process = subprocess.Popen(
            ['node', cline_core_path, '--port', str(self.cline_core_port),
             '--host-bridge-port', str(self.cline_host_port), '--config', str(self.config_path)],
            cwd=os.path.dirname(cline_core_path),
            env={
                "PATH": os.environ.get("PATH", ""),
                "NODE_PATH": node_path,
                "GRPC_TRACE": "all",
                "GRPC_VERBOSITY": "DEBUG",
                "NODE_ENV": "development"
            },
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True
        )

        instance = self.wait_for_instance()
        if instance is None:
            raise InstanceLockNotFoundError(f"Failed to find instance lock for port {self.cline_core_port} within timeout")
        return instance

    def stop(self) -> None:
        if self.core_process:
            self.core_process.terminate()
            self.core_process.wait()
            self.core_process = None

        if self.host_process:
            self.host_process.terminate()
            self.host_process.wait()
            self.host_process = None

    def is_running(self) -> bool:
        host_running = self.host_process is not None and self.host_process.poll() is None
        core_running = self.core_process is not None and self.core_process.poll() is None
        return host_running and core_running

    def wait_for_instance(self, timeout: int = 30) -> Optional[Instance]:
        db_path = Path(self.config_path) / "data" / "locks.db"
        held_by_variants = [
            f"localhost:{self.cline_core_port}",
            f"127.0.0.1:{self.cline_core_port}"
        ]

        logger.debug(f"Waiting for instance lock in database: {db_path}")
        logger.debug(f"Checking for held_by values: {held_by_variants}")

        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                if not os.path.exists(db_path):
                    logger.debug(f"Database file does not exist yet: {db_path}, waiting...")
                    time.sleep(0.5)
                    continue

                logger.debug(f"Connecting to database: {db_path}")

                with sqlite3.connect(db_path) as conn:
                    cursor = conn.cursor()

                    for held_by in held_by_variants:
                        logger.debug(f"Executing query for held_by='{held_by}', lock_type='instance'")
                        cursor.execute("""
                            SELECT held_by, lock_target, locked_at
                            FROM locks
                            WHERE held_by = ? AND lock_type = 'instance'
                        """, (held_by,))

                        result = cursor.fetchone()
                        logger.debug(f"Query result for held_by='{held_by}': {result}")

                        if result:
                            logger.debug(f"Found instance lock: address={result[0]}, lock_target={result[1]}, locked_at={result[2]}")
                            return Instance(
                                address=result[0],
                                lock_target=result[1],
                                locked_at=result[2]
                            )

                    logger.debug("No matching instance lock found in this iteration")

                time.sleep(0.5)  # Wait 500ms before retrying

            except sqlite3.Error as e:
                logger.debug(f"SQLite error while checking database: {e}, continuing to retry")
                # Database might be locked or corrupted, continue retrying
                time.sleep(0.5)

        logger.debug(f"Timeout exceeded ({timeout}s), no instance lock found")
        return None

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type: Optional[type], exc_val: Optional[Exception],
                  exc_tb: Optional[object]) -> None:
        self.stop()