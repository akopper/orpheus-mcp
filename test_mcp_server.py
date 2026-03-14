#!/usr/bin/env python3
"""
Tests for Orpheus MCP Server

Run with: python -m pytest test_mcp_server.py -v
Or: python test_mcp_server.py
"""

import os
import sys
import json
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Mock the TTS engine before importing mcp_server
sys.modules["tts_engine"] = MagicMock()
sys.modules["tts_engine.inference"] = MagicMock()

from tts_engine import AVAILABLE_VOICES, DEFAULT_VOICE, VOICE_TO_LANGUAGE
from tts_engine.inference import generate_speech_from_api

# Now import the MCP server
import mcp_server as mcp


class TestServerConfig:
    """Test ServerConfig class"""

    def test_default_config(self):
        """Test default configuration values"""
        config = mcp.ServerConfig()
        assert config.api_url == "http://127.0.0.1:1234/v1/completions"
        assert config.model_path is None
        assert config.llama_cpp_path is None
        assert config.auto_start_llama is True
        assert config.transport == "stdio"
        assert config.port == 5006
        assert config.output_dir == "outputs"

    @patch.dict(
        os.environ,
        {
            "ORPHEUS_API_URL": "http://custom:8080/v1/completions",
            "ORPHEUS_MODEL_PATH": "/path/to/model.gguf",
            "MCP_TRANSPORT": "sse",
            "MCP_PORT": "9000",
        },
        clear=True,
    )
    def test_config_from_env(self):
        """Test configuration loaded from environment variables"""
        config = mcp.get_config()
        assert config.api_url == "http://custom:8080/v1/completions"
        assert config.model_path == "/path/to/model.gguf"
        assert config.transport == "sse"
        assert config.port == 9000


class TestEstimateTokens:
    """Test token estimation function"""

    def test_empty_text(self):
        """Test estimation with empty text"""
        result = mcp.estimate_tokens("")
        assert result == 1  # Minimum 1 token

    def test_short_text(self):
        """Test estimation with short text"""
        text = "Hello world"
        result = mcp.estimate_tokens(text)
        # Roughly len(text) // 4 + 1
        expected = len(text) // 4 + 1
        assert result == expected

    def test_long_text(self):
        """Test estimation with longer text"""
        text = "This is a longer text that should be around 20 tokens or so when estimated."
        result = mcp.estimate_tokens(text)
        expected = len(text) // 4 + 1
        assert result == expected
        assert result > 10  # Should be more than 10 tokens


class TestLlamaServerManager:
    """Test LlamaServerManager class"""

    def test_init(self):
        """Test manager initialization"""
        config = mcp.ServerConfig()
        manager = mcp.LlamaServerManager(config)
        assert manager.config == config
        assert manager.process is None
        assert manager.server_ready is False

    @patch("mcp_server.requests.get")
    def test_is_server_running_true(self, mock_get):
        """Test detecting running server"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        config = mcp.ServerConfig()
        manager = mcp.LlamaServerManager(config)

        result = manager.is_server_running()
        assert result is True
        mock_get.assert_called_once()

    @patch("mcp_server.requests.get")
    def test_is_server_running_false(self, mock_get):
        """Test detecting stopped server"""
        mock_get.side_effect = Exception("Connection refused")

        config = mcp.ServerConfig()
        manager = mcp.LlamaServerManager(config)

        result = manager.is_server_running()
        assert result is False


class TestToolHandlers:
    """Test MCP tool handlers"""

    @pytest.mark.asyncio
    async def test_handle_list_voices(self):
        """Test list_voices tool"""
        result = await mcp.handle_list_voices()

        assert len(result) == 1
        assert result[0].type == "text"

        # Parse JSON response
        data = json.loads(result[0].text)
        assert "voices" in data
        assert "total" in data
        assert "default" in data
        assert data["total"] == len(AVAILABLE_VOICES)
        assert data["default"] == DEFAULT_VOICE

    @pytest.mark.asyncio
    async def test_handle_get_voice_info_valid(self):
        """Test get_voice_info with valid voice"""
        result = await mcp.handle_get_voice_info({"voice": "tara"})

        assert len(result) == 1
        assert result[0].type == "text"

        data = json.loads(result[0].text)
        assert data["name"] == "tara"
        assert "language" in data
        assert "supported_emotions" in data
        assert data["sample_rate_hz"] == 24000

    @pytest.mark.asyncio
    async def test_handle_get_voice_info_invalid(self):
        """Test get_voice_info with invalid voice"""
        result = await mcp.handle_get_voice_info({"voice": "invalid_voice"})

        assert len(result) == 1
        assert result[0].type == "text"
        assert "Error" in result[0].text

    @pytest.mark.asyncio
    async def test_handle_estimate_tokens(self):
        """Test estimate_tokens tool"""
        text = "Hello world, this is a test sentence for token estimation."
        result = await mcp.handle_estimate_tokens({"text": text})

        assert len(result) == 1
        assert result[0].type == "text"

        data = json.loads(result[0].text)
        assert "text_length" in data
        assert "estimated_tokens" in data
        assert "max_tokens" in data
        assert "fits_in_single_request" in data
        assert data["text_length"] == len(text)

    @pytest.mark.asyncio
    async def test_handle_estimate_tokens_empty(self):
        """Test estimate_tokens with empty text"""
        result = await mcp.handle_estimate_tokens({"text": ""})

        assert len(result) == 1
        assert result[0].type == "text"
        assert "Error" in result[0].text

    @pytest.mark.asyncio
    @patch("mcp_server.generate_speech_from_api")
    async def test_handle_generate_speech_success(self, mock_generate):
        """Test generate_speech with valid input"""
        # Mock the generation
        mock_generate.return_value = [b"fake_audio_data"]

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("mcp_server.config") as mock_config:
                mock_config.output_dir = tmpdir

                result = await mcp.handle_generate_speech(
                    {
                        "text": "Hello world",
                        "voice": "tara",
                    }
                )

                assert len(result) == 1
                assert result[0].type == "text"

                data = json.loads(result[0].text)
                assert data["success"] is True
                assert data["voice"] == "tara"
                assert "output_path" in data

    @pytest.mark.asyncio
    async def test_handle_generate_speech_missing_text(self):
        """Test generate_speech with missing text"""
        result = await mcp.handle_generate_speech({})

        assert len(result) == 1
        assert result[0].type == "text"
        assert "Error" in result[0].text

    @pytest.mark.asyncio
    async def test_handle_generate_speech_invalid_voice(self):
        """Test generate_speech with invalid voice"""
        result = await mcp.handle_generate_speech(
            {
                "text": "Hello",
                "voice": "nonexistent_voice",
            }
        )

        assert len(result) == 1
        assert result[0].type == "text"
        assert "Error" in result[0].text


class TestToolDefinitions:
    """Test tool schema definitions"""

    @pytest.mark.asyncio
    async def test_list_tools(self):
        """Test that all tools are defined"""
        tools = await mcp.list_tools()

        tool_names = [tool.name for tool in tools]
        assert "generate_speech" in tool_names
        assert "list_voices" in tool_names
        assert "get_voice_info" in tool_names
        assert "estimate_tokens" in tool_names

        # Check generate_speech schema
        gen_speech = next(t for t in tools if t.name == "generate_speech")
        assert "text" in gen_speech.inputSchema["properties"]
        assert "voice" in gen_speech.inputSchema["properties"]
        assert "output_path" in gen_speech.inputSchema["properties"]
        assert "streaming" in gen_speech.inputSchema["properties"]


class TestIntegration:
    """Integration tests"""

    @pytest.mark.asyncio
    async def test_full_workflow(self):
        """Test complete workflow: estimate -> list voices -> generate"""
        # Step 1: Estimate tokens
        text = "Hello world, this is a test."
        estimate_result = await mcp.handle_estimate_tokens({"text": text})
        estimate_data = json.loads(estimate_result[0].text)
        assert estimate_data["fits_in_single_request"] is True

        # Step 2: List voices
        voices_result = await mcp.handle_list_voices()
        voices_data = json.loads(voices_result[0].text)
        assert voices_data["total"] > 0

        # Step 3: Get voice info
        voice_info_result = await mcp.handle_get_voice_info({"voice": DEFAULT_VOICE})
        voice_info_data = json.loads(voice_info_result[0].text)
        assert voice_info_data["name"] == DEFAULT_VOICE


def run_sync_tests():
    """Run synchronous tests"""
    print("\n=== Running Synchronous Tests ===\n")

    # Test ServerConfig
    config_test = TestServerConfig()
    config_test.test_default_config()
    print("✓ test_default_config passed")

    config_test.test_config_from_env()
    print("✓ test_config_from_env passed")

    # Test EstimateTokens
    estimate_test = TestEstimateTokens()
    estimate_test.test_empty_text()
    print("✓ test_empty_text passed")

    estimate_test.test_short_text()
    print("✓ test_short_text passed")

    estimate_test.test_long_text()
    print("✓ test_long_text passed")

    print("\n=== All Synchronous Tests Passed ===\n")


async def run_async_tests():
    """Run asynchronous tests"""
    print("\n=== Running Asynchronous Tests ===\n")

    # Test ToolHandlers
    handlers_test = TestToolHandlers()

    await handlers_test.test_handle_list_voices()
    print("✓ test_handle_list_voices passed")

    await handlers_test.test_handle_get_voice_info_valid()
    print("✓ test_handle_get_voice_info_valid passed")

    await handlers_test.test_handle_get_voice_info_invalid()
    print("✓ test_handle_get_voice_info_invalid passed")

    await handlers_test.test_handle_estimate_tokens()
    print("✓ test_handle_estimate_tokens passed")

    await handlers_test.test_handle_estimate_tokens_empty()
    print("✓ test_handle_estimate_tokens_empty passed")

    await handlers_test.test_handle_generate_speech_missing_text()
    print("✓ test_handle_generate_speech_missing_text passed")

    await handlers_test.test_handle_generate_speech_invalid_voice()
    print("✓ test_handle_generate_speech_invalid_voice passed")

    # Test ToolDefinitions
    definitions_test = TestToolDefinitions()
    await definitions_test.test_list_tools()
    print("✓ test_list_tools passed")

    # Test Integration
    integration_test = TestIntegration()
    await integration_test.test_full_workflow()
    print("✓ test_full_workflow passed")

    print("\n=== All Asynchronous Tests Passed ===\n")


if __name__ == "__main__":
    import pytest

    # Check if pytest is available
    try:
        # Run with pytest if available
        pytest.main([__file__, "-v"])
    except ImportError:
        # Fallback to manual test runner
        print("Running tests without pytest...")

        # Run sync tests
        run_sync_tests()

        # Run async tests
        asyncio.run(run_async_tests())

        print("\n" + "=" * 50)
        print("All tests passed!")
        print("=" * 50 + "\n")
