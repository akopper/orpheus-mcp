#!/usr/bin/env bash
# Integration tests for Orpheus MCP Server via mcporter
# Run with: ./test_mcporter_integration.sh

set -e  # Exit on error

echo "=========================================="
echo "Orpheus MCP Server Integration Tests"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0

# Helper function to run a test
run_test() {
    local test_name="$1"
    local test_cmd="$2"
    local expected_pattern="$3"
    
    echo -n "Testing: $test_name... "
    
    if output=$(eval "$test_cmd" 2>&1); then
        if echo "$output" | grep -q "$expected_pattern"; then
            echo -e "${GREEN}PASSED${NC}"
            TESTS_PASSED=$((TESTS_PASSED + 1))
            return 0
        else
            echo -e "${RED}FAILED${NC} (output didn't match expected pattern)"
            echo "  Output: $output"
            TESTS_FAILED=$((TESTS_FAILED + 1))
            return 1
        fi
    else
        echo -e "${RED}FAILED${NC} (command failed)"
        echo "  Output: $output"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

# Test 1: List voices
run_test "list_voices" \
    "mcporter call orpheus-tts.list_voices" \
    '"name": "tara"'

# Test 2: Get voice info for tara
run_test "get_voice_info (tara)" \
    "mcporter call orpheus-tts.get_voice_info voice=tara" \
    '"name": "tara"'

# Test 3: Get voice info for leah
run_test "get_voice_info (leah)" \
    "mcporter call orpheus-tts.get_voice_info voice=leah" \
    '"name": "leah"'

# Test 4: Estimate tokens for short text
run_test "estimate_tokens (short)" \
    "mcporter call orpheus-tts.estimate_tokens text='Hello world'" \
    '"fits_in_single_request": true'

# Test 5: Error handling - invalid voice
run_test "error_handling (invalid voice)" \
    "mcporter call orpheus-tts.get_voice_info voice=invalid_voice" \
    "is not one of"

# Test 6: Generate speech (short text) - requires llama.cpp server running
echo -n "Testing: generate_speech (short)... "
# Clean up any previous test file
rm -f outputs/test_hello.wav

if output=$(mcporter call orpheus-tts.generate_speech text="Hello" voice=tara output_path=outputs/test_hello.wav 2>&1); then
    if echo "$output" | grep -q '"success": true'; then
        # Check if file was actually created and has content
        if [ -f "outputs/test_hello.wav" ] && [ -s "outputs/test_hello.wav" ]; then
            file_size=$(stat -f%z "outputs/test_hello.wav" 2>/dev/null || stat -c%s "outputs/test_hello.wav" 2>/dev/null)
            echo -e "${GREEN}PASSED${NC}"
            echo "  ✓ Audio file created: outputs/test_hello.wav (${file_size} bytes)"
            TESTS_PASSED=$((TESTS_PASSED + 1))
        else
            echo -e "${RED}FAILED${NC} (file not created or empty)"
            echo "  Output: $output"
            TESTS_FAILED=$((TESTS_FAILED + 1))
        fi
    else
        echo -e "${RED}FAILED${NC} (generation failed)"
        echo "  Output: $output"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
else
    echo -e "${RED}FAILED${NC} (command failed - llama.cpp server may not be running)"
    echo "  Output: $output"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

# Summary
echo ""
echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo -e "Tests Passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Tests Failed: ${RED}$TESTS_FAILED${NC}"
echo "Total Tests: $((TESTS_PASSED + TESTS_FAILED))"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed.${NC}"
    exit 1
fi
