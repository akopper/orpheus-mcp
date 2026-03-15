# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Stream liveness timeout to prevent hanging requests when the token stream stalls
  - Configurable via `ORPHEUS_STREAM_TIMEOUT` (default: 15 seconds)
  - Supports duration strings: `15`, `15s`, `1m30s`, etc.
  - If no tokens received within timeout, generation stops gracefully
- Idle timeout watchdog to automatically stop llama-server when idle
  - Configurable via `ORPHEUS_IDLE_TIMEOUT` (default: 5 minutes / `5m`)
  - Supports duration strings: `300`, `5m`, `1h30m`, etc.
  - Frees system resources (RAM/VRAM) when not in use
  - Server automatically restarts on next request
- Support for mcporter daemon with `lifecycle: "keep-alive"` configuration
- Duration string parsing utility for flexible timeout configuration
  - Follows Ollama/Docker conventions

### Changed
- Fail-fast error handling: removed retry logic for cleaner failure handling
  - Client should handle retries if needed
- Better error messages for stream timeout and idle timeout conditions

### Fixed
- Fixed issue where requests would hang indefinitely while files were being created
  - Stream now has explicit liveness monitoring
  - Partial results are treated as errors (no silent failures)

### Documentation
- Added pitfall documentation for slow hardware in README
- Updated AGENTS.md with new behavior and changelog update instructions

## [0.1.0] - Initial Release

### Added
- MCP server for Orpheus TTS
- Support for 25 voices across 8 languages
- Voice cloning capabilities
- Automatic llama.cpp server management