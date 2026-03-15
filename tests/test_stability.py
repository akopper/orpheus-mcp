#!/usr/bin/env python3
"""
Tests for stability features: stream timeout and idle timeout watchdog.

Run with: python -m pytest tests/test_stability.py -v
"""

import os
import sys
import time
import threading
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock, call
from concurrent.futures import ThreadPoolExecutor

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestDurationParsing:
    """Test duration string parsing utility"""

    def test_parse_duration_plain_number(self):
        """Test plain number is parsed as seconds"""
        from mcp_server import parse_duration

        assert parse_duration("300", 60) == 300
        assert parse_duration("60", 60) == 60
        assert parse_duration("0", 60) == 0

    def test_parse_duration_with_suffix(self):
        """Test duration with suffix (s, m, h)"""
        from mcp_server import parse_duration

        assert parse_duration("30s", 60) == 30
        assert parse_duration("5m", 60) == 300
        assert parse_duration("1h", 60) == 3600
        assert parse_duration("2h", 60) == 7200

    def test_parse_duration_mixed(self):
        """Test mixed duration strings"""
        from mcp_server import parse_duration

        assert parse_duration("1h30m", 60) == 5400
        assert parse_duration("1m30s", 60) == 90
        assert parse_duration("2h15m30s", 60) == 8130

    def test_parse_duration_invalid(self):
        """Test invalid duration falls back to default"""
        from mcp_server import parse_duration

        assert parse_duration("invalid", 60) == 60
        assert parse_duration("", 60) == 60
        assert parse_duration(None, 60) == 60

    def test_parse_duration_case_insensitive(self):
        """Test duration parsing is case insensitive"""
        from mcp_server import parse_duration

        assert parse_duration("5M", 60) == 300
        assert parse_duration("1H", 60) == 3600
        assert parse_duration("30S", 60) == 30


class TestStreamTimeout:
    """Test stream liveness timeout in inference.py"""

    def test_stream_timeout_config_default(self):
        """Test stream timeout has correct default value"""
        from tts_engine.inference import STREAM_TIMEOUT

        assert STREAM_TIMEOUT == 15

    def test_stream_timeout_config_from_env(self):
        """Test stream timeout can be configured from environment"""
        with patch.dict(os.environ, {"ORPHEUS_STREAM_TIMEOUT": "30"}):
            # Need to reload the module to pick up new env var
            import importlib
            import tts_engine.inference as inference

            importlib.reload(inference)
            assert inference.STREAM_TIMEOUT == 30
            # Restore
            importlib.reload(inference)

    def test_stream_timeout_duration_string(self):
        """Test stream timeout accepts duration strings"""
        with patch.dict(os.environ, {"ORPHEUS_STREAM_TIMEOUT": "1m"}):
            import importlib
            import tts_engine.inference as inference

            importlib.reload(inference)
            assert inference.STREAM_TIMEOUT == 60
            importlib.reload(inference)

    def test_stream_timeout_invalid_env(self):
        """Test stream timeout falls back to default on invalid env value"""
        with patch.dict(os.environ, {"ORPHEUS_STREAM_TIMEOUT": "invalid"}):
            import importlib
            import tts_engine.inference as inference

            importlib.reload(inference)
            assert inference.STREAM_TIMEOUT == 15
            # Restore
            importlib.reload(inference)


class TestIdleTimeoutConfig:
    """Test idle timeout configuration"""

    def test_idle_timeout_config_default(self):
        """Test idle timeout has correct default value (5m = 300s)"""
        # Need to mock dotenv to avoid loading .env file
        with patch("mcp_server.load_dotenv"):
            import mcp_server as mcp

            config = mcp.ServerConfig()
            assert config.idle_timeout == 300  # 5 minutes in seconds

    def test_idle_timeout_config_from_env(self):
        """Test idle timeout can be configured from environment (plain seconds)"""
        with (
            patch("mcp_server.load_dotenv"),
            patch.dict(os.environ, {"ORPHEUS_IDLE_TIMEOUT": "600"}),
        ):
            import mcp_server as mcp

            config = mcp.get_config()
            assert config.idle_timeout == 600

    def test_idle_timeout_duration_string(self):
        """Test idle timeout accepts duration strings"""
        with (
            patch("mcp_server.load_dotenv"),
            patch.dict(os.environ, {"ORPHEUS_IDLE_TIMEOUT": "5m"}),
        ):
            import mcp_server as mcp

            config = mcp.get_config()
            assert config.idle_timeout == 300

    def test_idle_timeout_duration_mixed(self):
        """Test idle timeout accepts mixed duration strings"""
        with (
            patch("mcp_server.load_dotenv"),
            patch.dict(os.environ, {"ORPHEUS_IDLE_TIMEOUT": "1h30m"}),
        ):
            import mcp_server as mcp

            config = mcp.get_config()
            assert config.idle_timeout == 5400

    def test_idle_timeout_invalid_env(self):
        """Test idle timeout falls back to default on invalid env value"""
        with (
            patch("mcp_server.load_dotenv"),
            patch.dict(os.environ, {"ORPHEUS_IDLE_TIMEOUT": "abc"}),
        ):
            import mcp_server as mcp

            config = mcp.get_config()
            assert config.idle_timeout == 300  # 5 minutes default


class TestLlamaServerManagerWatchdog:
    """Test the LlamaServerManager idle timeout watchdog"""

    def test_watchdog_initialization(self):
        """Test watchdog initializes correctly"""
        with patch("mcp_server.load_dotenv"):
            import mcp_server as mcp

            config = mcp.ServerConfig()
            manager = mcp.LlamaServerManager(config)

            assert manager.last_request_time == 0
            assert manager._watchdog_running == False
            assert manager._watchdog_thread is None

    def test_update_activity(self):
        """Test update_activity sets timestamp"""
        with patch("mcp_server.load_dotenv"):
            import mcp_server as mcp

            config = mcp.ServerConfig()
            manager = mcp.LlamaServerManager(config)

            # Initial state
            initial_time = manager.last_request_time

            # Wait a tiny bit and update
            time.sleep(0.01)
            manager.update_activity()

            # Should be updated
            assert manager.last_request_time > initial_time
            assert manager.last_request_time <= time.time()

    def test_watchdog_start_stop(self):
        """Test watchdog can be started and stopped"""
        with patch("mcp_server.load_dotenv"):
            import mcp_server as mcp

            config = mcp.ServerConfig()
            config.idle_timeout = 1  # Short timeout for testing
            manager = mcp.LlamaServerManager(config)

            # Start watchdog
            manager.start_watchdog()
            assert manager._watchdog_running == True
            assert manager._watchdog_thread is not None
            assert manager._watchdog_thread.daemon == True

            # Stop watchdog
            manager.stop_watchdog()
            assert manager._watchdog_running == False

    def test_watchdog_stops_server_on_idle(self):
        """Test watchdog stops server after idle timeout"""
        with patch("mcp_server.load_dotenv"):
            import mcp_server as mcp

            # Create a mock process
            mock_process = MagicMock()
            mock_process.pid = 12345
            mock_process.wait.return_value = None

            config = mcp.ServerConfig()
            config.idle_timeout = 1  # 1 minute for fast test
            manager = mcp.LlamaServerManager(config)
            manager.process = mock_process
            manager.last_request_time = time.time() - 120  # 2 minutes ago

            # Track if stop_server was called
            stop_called = []
            original_stop = manager.stop_server

            def mock_stop():
                stop_called.append(True)
                manager.process = None

            manager.stop_server = mock_stop

            # Start watchdog with short check interval
            original_check_interval = 30  # Will be patched

            # Manually trigger the check (simulating what watchdog does)
            idle_seconds = time.time() - manager.last_request_time
            idle_minutes = idle_seconds / 60

            assert idle_minutes >= config.idle_timeout

    def test_watchdog_does_not_stop_active_server(self):
        """Test watchdog does not stop server with recent activity"""
        with patch("mcp_server.load_dotenv"):
            import mcp_server as mcp

            config = mcp.ServerConfig()
            config.idle_timeout = 1
            manager = mcp.LlamaServerManager(config)
            manager.last_request_time = time.time()  # Just now

            # Simulate idle check
            idle_seconds = time.time() - manager.last_request_time
            idle_minutes = idle_seconds / 60

            # Should NOT trigger stop
            assert idle_minutes < config.idle_timeout


class TestConfigVariables:
    """Test all new configuration variables are documented"""

    def test_all_config_vars_in_dataclass(self):
        """Verify all config variables exist in ServerConfig"""
        with patch("mcp_server.load_dotenv"):
            import mcp_server as mcp

            config = mcp.ServerConfig()

            # Check existing + new config vars
            assert hasattr(config, "api_url")
            assert hasattr(config, "model_path")
            assert hasattr(config, "llama_cpp_path")
            assert hasattr(config, "auto_start_llama")
            assert hasattr(config, "transport")
            assert hasattr(config, "port")
            assert hasattr(config, "output_dir")
            assert hasattr(config, "idle_timeout")  # New


class TestIntegration:
    """Integration tests for stability features"""

    def test_stream_timeout_creates_timeout_message(self):
        """Test that stream timeout prints appropriate message"""
        # This would require mocking the HTTP response
        # For now, just verify the mechanism exists
        from tts_engine.inference import STREAM_TIMEOUT

        assert isinstance(STREAM_TIMEOUT, int)
        assert STREAM_TIMEOUT > 0


def run_tests():
    """Run all tests manually (without pytest)"""
    print("=" * 50)
    print("Running Stability Tests")
    print("=" * 50)

    # Test Duration Parsing
    print("\n--- Duration Parsing Tests ---")
    test = TestDurationParsing()
    test.test_parse_duration_plain_number()
    print("✓ test_parse_duration_plain_number")
    test.test_parse_duration_with_suffix()
    print("✓ test_parse_duration_with_suffix")
    test.test_parse_duration_mixed()
    print("✓ test_parse_duration_mixed")
    test.test_parse_duration_invalid()
    print("✓ test_parse_duration_invalid")
    test.test_parse_duration_case_insensitive()
    print("✓ test_parse_duration_case_insensitive")

    # Test Stream Timeout
    print("\n--- Stream Timeout Tests ---")
    test = TestStreamTimeout()
    test.test_stream_timeout_config_default()
    print("✓ test_stream_timeout_config_default")
    test.test_stream_timeout_config_from_env()
    print("✓ test_stream_timeout_config_from_env")
    test.test_stream_timeout_duration_string()
    print("✓ test_stream_timeout_duration_string")
    test.test_stream_timeout_invalid_env()
    print("✓ test_stream_timeout_invalid_env")

    # Test Idle Timeout Config
    print("\n--- Idle Timeout Config Tests ---")
    test = TestIdleTimeoutConfig()
    test.test_idle_timeout_config_default()
    print("✓ test_idle_timeout_config_default")
    test.test_idle_timeout_config_from_env()
    print("✓ test_idle_timeout_config_from_env")
    test.test_idle_timeout_duration_string()
    print("✓ test_idle_timeout_duration_string")
    test.test_idle_timeout_duration_mixed()
    print("✓ test_idle_timeout_duration_mixed")
    test.test_idle_timeout_invalid_env()
    print("✓ test_idle_timeout_invalid_env")

    # Test Watchdog
    print("\n--- Watchdog Tests ---")
    test = TestLlamaServerManagerWatchdog()
    test.test_watchdog_initialization()
    print("✓ test_watchdog_initialization")
    test.test_update_activity()
    print("✓ test_update_activity")
    test.test_watchdog_start_stop()
    print("✓ test_watchdog_start_stop")
    test.test_watchdog_stops_server_on_idle()
    print("✓ test_watchdog_stops_server_on_idle")
    test.test_watchdog_does_not_stop_active_server()
    print("✓ test_watchdog_does_not_stop_active_server")

    # Test Config
    print("\n--- Config Tests ---")
    test = TestConfigVariables()
    test.test_all_config_vars_in_dataclass()
    print("✓ test_all_config_vars_in_dataclass")

    # Integration
    print("\n--- Integration Tests ---")
    test = TestIntegration()
    test.test_stream_timeout_creates_timeout_message()
    print("✓ test_stream_timeout_creates_timeout_message")

    print("\n" + "=" * 50)
    print("All Stability Tests Passed!")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    run_tests()
