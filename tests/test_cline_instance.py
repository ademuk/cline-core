import sqlite3
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from cline_core.cline_instance import (
    ClineInstance,
    Instance,
    find_available_port_pair,
    get_cline_core_path,
    InstanceLockNotFoundError
)


class TestGetClineCorePath:
    @patch('subprocess.check_output')
    @patch('os.path.exists')
    def test_get_cline_core_path_global_install(self, mock_exists, mock_check_output):
        """Test finding cline-core.js in global node_modules."""
        mock_check_output.return_value = "/usr/local/lib/node_modules\n"
        mock_exists.return_value = True

        path = get_cline_core_path()
        expected = "/usr/local/lib/node_modules/cline/cline-core.js"

        assert path == expected
        mock_check_output.assert_called_once_with(['npm', 'root', '-g'], text=True)
        mock_exists.assert_called_once_with(expected)

    @patch('subprocess.check_output', side_effect=subprocess.CalledProcessError(1, 'npm'))
    def test_get_cline_core_path_no_global_install(self, mock_check_output):
        """Test behavior when global install is not found."""
        with pytest.raises(FileNotFoundError, match="cline-core.js not found"):
            get_cline_core_path()

    @patch('subprocess.check_output', side_effect=FileNotFoundError())
    def test_get_cline_core_path_no_npm(self, mock_check_output):
        """Test behavior when npm is not available."""
        with pytest.raises(FileNotFoundError, match="cline-core.js not found"):
            get_cline_core_path()


class TestFindAvailablePortPair:
    @patch('socket.socket')
    def test_find_available_port_pair(self, mock_socket_class):
        """Test finding available port pairs."""
        # Create mock sockets
        host_socket = Mock()
        host_socket.getsockname.return_value = ('', 8080)
        host_socket.bind = Mock()
        host_socket.close = Mock()

        core_socket = Mock()
        core_socket.getsockname.return_value = ('', 9090)
        core_socket.bind = Mock()
        core_socket.close = Mock()

        mock_socket_class.side_effect = [host_socket, core_socket]

        host_port, core_port = find_available_port_pair()

        assert host_port == 8080
        assert core_port == 9090

        # Should create 2 socket instances
        assert mock_socket_class.call_count == 2

        # Should bind both sockets
        host_socket.bind.assert_called_once_with(('', 0))
        core_socket.bind.assert_called_once_with(('', 0))

        # Should close both sockets
        host_socket.close.assert_called_once()
        core_socket.close.assert_called_once()


class TestClineInstance:
    """Test ClineInstance class."""

    @patch('cline_core.cline_instance.get_cline_core_path')
    @patch('cline_core.cline_instance.find_available_port_pair')
    def test_with_available_ports_classmethod(self, mock_find_ports, mock_get_core_path):
        """Test with_available_ports classmethod."""
        mock_find_ports.return_value = (8080, 9090)
        mock_get_core_path.return_value = "/fake/path/cline-core.js"

        instance = ClineInstance.with_available_ports()

        assert instance.cline_host_port == 8080
        assert instance.cline_core_port == 9090
        assert instance.config_path == Path.home() / ".cline"
        assert instance.cwd == Path.cwd()
        assert instance.host_process is None
        assert instance.core_process is None

        mock_find_ports.assert_called_once()

    @patch('cline_core.cline_instance.get_cline_core_path')
    @patch('cline_core.cline_instance.find_available_port_pair')
    def test_with_available_ports_custom_params(self, mock_find_ports, mock_get_core_path):
        """Test with_available_ports with custom parameters."""
        mock_find_ports.return_value = (8080, 9090)
        custom_cwd = Path("/custom/cwd")
        custom_config = Path("/custom/config")

        instance = ClineInstance.with_available_ports(cwd=custom_cwd, config_path=custom_config)

        assert instance.cline_host_port == 8080
        assert instance.cline_core_port == 9090
        assert instance.config_path == custom_config
        assert instance.cwd == custom_cwd

    def test_constructor(self):
        """Test ClineInstance constructor."""
        custom_config = Path("/custom/config")
        custom_cwd = Path("/custom/cwd")

        instance = ClineInstance(
            cline_host_port=8080,
            cline_core_port=9090,
            config_path=custom_config,
            cwd=custom_cwd
        )

        assert instance.cline_host_port == 8080
        assert instance.cline_core_port == 9090
        assert instance.config_path == custom_config
        assert instance.cwd == custom_cwd
        assert instance.host_process is None
        assert instance.core_process is None

    def test_is_running_no_processes(self):
        """Test is_running when no processes are started."""
        instance = ClineInstance(8080, 9090, None, Path.cwd())

        assert not instance.is_running()

    @patch('cline_core.cline_instance.ClineInstance.wait_for_instance')
    @patch('subprocess.Popen')
    @patch('cline_core.cline_instance.get_cline_core_path')
    def test_is_running_processes_running(self, mock_get_core_path, mock_popen, mock_wait_for_instance):
        """Test is_running when processes are running."""
        mock_get_core_path.return_value = "/fake/path/cline-core.js"
        mock_wait_for_instance.return_value = Instance("127.0.0.1:9090", "target", "timestamp")

        host_process = Mock()
        host_process.poll.return_value = None  # Process still running

        core_process = Mock()
        core_process.poll.return_value = None  # Process still running

        mock_popen.side_effect = [host_process, core_process]

        instance = ClineInstance(8080, 9090, None, Path.cwd())
        instance.start()  # This sets host_process and core_process

        assert instance.is_running()

        host_process.poll.assert_called_once()
        core_process.poll.assert_called_once()

    @patch('cline_core.cline_instance.ClineInstance.wait_for_instance')
    @patch('subprocess.Popen')
    @patch('cline_core.cline_instance.get_cline_core_path')
    def test_is_running_processes_exited(self, mock_get_core_path, mock_popen, mock_wait_for_instance):
        """Test is_running when processes have exited."""
        mock_get_core_path.return_value = "/fake/path/cline-core.js"
        mock_wait_for_instance.return_value = Instance("127.0.0.1:9090", "target", "timestamp")

        host_process = Mock()
        host_process.poll.return_value = 0  # Process exited normally

        core_process = Mock()
        core_process.poll.return_value = 0  # Process exited normally

        mock_popen.side_effect = [host_process, core_process]

        instance = ClineInstance(8080, 9090, None, Path.cwd())
        instance.start()  # This sets host_process and core_process

        assert not instance.is_running()

        host_process.poll.assert_called_once()
        core_process.poll.assert_called_once()

    def test_stop_without_processes(self):
        """Test stop when no processes are running."""
        instance = ClineInstance(8080, 9090, None, Path.cwd())

        # Should not raise any errors
        instance.stop()

        assert instance.host_process is None
        assert instance.core_process is None

    @patch('cline_core.cline_instance.ClineInstance.wait_for_instance')
    @patch('subprocess.Popen')
    @patch('cline_core.cline_instance.get_cline_core_path')
    def test_stop_with_processes(self, mock_get_core_path, mock_popen, mock_wait_for_instance):
        """Test stop when processes are running."""
        mock_get_core_path.return_value = "/fake/path/cline-core.js"
        mock_wait_for_instance.return_value = Instance("127.0.0.1:9090", "target", "timestamp")

        host_process = Mock()
        core_process = Mock()

        mock_popen.side_effect = [host_process, core_process]

        instance = ClineInstance(8080, 9090, None, Path.cwd())
        instance.start()

        instance.stop()

        # Processes should be terminated and have wait() called
        host_process.terminate.assert_called_once()
        host_process.wait.assert_called_once()

        core_process.terminate.assert_called_once()
        core_process.wait.assert_called_once()

        # Process references should be cleared
        assert instance.host_process is None
        assert instance.core_process is None

    def test_wait_for_instance_timeout(self, tmp_path):
        """Test wait_for_instance when timeout is reached."""
        instance = ClineInstance(8080, 9090, tmp_path, Path.cwd())

        result = instance.wait_for_instance(timeout=0.1)  # Very short timeout

        assert result is None

    def test_wait_for_instance_database_not_exists(self, tmp_path):
        """Test wait_for_instance when database doesn't exist."""
        instance = ClineInstance(8080, 9090, tmp_path, Path.cwd())

        result = instance.wait_for_instance(timeout=0.1)  # Very short timeout

        assert result is None

    @patch('os.path.exists')
    @patch('sqlite3.connect')
    @patch('time.sleep')
    def test_wait_for_instance_found(self, mock_sleep, mock_connect, mock_exists, tmp_path):
        """Test wait_for_instance when instance is found in database."""
        mock_exists.return_value = True

        # Mock cursor and connection
        mock_cursor = Mock()
        mock_connection = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_connect.return_value.__enter__ = Mock(return_value=mock_connection)
        mock_connect.return_value.__exit__ = Mock(return_value=False)

        # Mock database query result - returns None for localhost, then the result for 127.0.0.1
        def fetchone_side_effect():
            if mock_cursor.execute.call_count == 1:
                return None  # localhost query returns no result
            else:
                return ('127.0.0.1:9090', 'target_value', 'timestamp')  # 127.0.0.1 query returns result

        mock_cursor.fetchone.side_effect = fetchone_side_effect

        instance = ClineInstance(8080, 9090, tmp_path, Path.cwd())
        result = instance.wait_for_instance(timeout=1.0)

        assert result is not None
        assert result.address == '127.0.0.1:9090'
        assert result.lock_target == 'target_value'
        assert result.locked_at == 'timestamp'

        # Verify correct query was executed for localhost first, then 127.0.0.1
        from unittest.mock import call
        mock_cursor.execute.assert_has_calls([
            call("""
                            SELECT held_by, lock_target, locked_at
                            FROM locks
                            WHERE held_by = ? AND lock_type = 'instance'
                        """, ('localhost:9090',)),
            call("""
                            SELECT held_by, lock_target, locked_at
                            FROM locks
                            WHERE held_by = ? AND lock_type = 'instance'
                        """, ('127.0.0.1:9090',))
        ])

    @patch('os.path.exists')
    @patch('sqlite3.connect')
    @patch('time.sleep')
    def test_wait_for_instance_sqlite_error(self, mock_sleep, mock_connect, mock_exists, tmp_path):
        """Test wait_for_instance handles SQLite errors gracefully."""
        mock_exists.return_value = True
        mock_connect.side_effect = sqlite3.Error("Database locked")

        instance = ClineInstance(8080, 9090, tmp_path, Path.cwd())
        result = instance.wait_for_instance(timeout=0.2)

        assert result is None

    def test_context_manager(self, tmp_path):
        """Test ClineInstance as context manager."""
        with patch.object(ClineInstance, '__enter__', return_value=Mock()) as mock_enter:
            with patch.object(ClineInstance, '__exit__') as mock_exit:
                config_path = tmp_path / "config"
                cwd_path = tmp_path / "cwd"

                instance = ClineInstance(8080, 9090, config_path, cwd_path)

                with instance:
                    mock_enter.assert_called_once()
                    mock_exit.assert_not_called()

                mock_exit.assert_called_once_with(None, None, None)

    @patch('cline_core.cline_instance.ClineInstance.start')
    @patch('cline_core.cline_instance.ClineInstance.stop')
    def test_context_manager_exception(self, mock_stop, mock_start):
        """Test context manager handles exceptions properly."""
        mock_start.return_value = Mock()
        mock_stop.return_value = None

        instance = ClineInstance(8080, 9090, None, Path.cwd())

        try:
            with instance:
                raise ValueError("Test exception")
        except ValueError:
            pass

        # stop should still be called even with exception
        mock_stop.assert_called_once()


class TestInstanceDataclass:
    """Test Instance dataclass."""

    def test_instance_creation(self):
        """Test Instance dataclass creation."""
        instance = Instance(
            address="127.0.0.1:9090",
            lock_target="some-target",
            locked_at="2023-01-01 00:00:00"
        )

        assert instance.address == "127.0.0.1:9090"
        assert instance.lock_target == "some-target"
        assert instance.locked_at == "2023-01-01 00:00:00"

    def test_instance_equality(self):
        """Test Instance equality comparison."""
        instance1 = Instance("127.0.0.1:9090", "target1", "time1")
        instance2 = Instance("127.0.0.1:9090", "target1", "time1")
        instance3 = Instance("127.0.0.1:8080", "target2", "time2")

        assert instance1 == instance2
        assert instance1 != instance3


class TestInstanceLockNotFoundError:
    """Test InstanceLockNotFoundError exception."""

    def test_exception_creation(self):
        """Test creating InstanceLockNotFoundError."""
        error = InstanceLockNotFoundError("Custom error message")

        assert str(error) == "Custom error message"
        assert isinstance(error, Exception)


# Tests for removed client modules have been removed
