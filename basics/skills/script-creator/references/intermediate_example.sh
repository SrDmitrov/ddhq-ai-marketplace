#!/bin/bash

# Intermediate Coffee Making Script
# What an experienced senior dev writes when automating for their team
# Features: main function, methods (SOLID style), basic error handling, user input

set -euo pipefail  # Exit on error, undefined vars, pipe failures

# ============================================================================
# Configuration
# ============================================================================

CUPS=${1:-1}
COFFEE_TYPE="arabica"
WATER_TEMP=95
SCRIPT_NAME="$(basename "$0")"

# ============================================================================
# Logging Functions - simple echo style
# ============================================================================

log_step() {
    echo ""
    echo ">>> $1"
}

log_success() {
    echo "✓ $1"
}

log_error() {
    echo "✗ ERROR: $1" >&2
}

# ============================================================================
# Utility Functions
# ============================================================================

require_resources() {
    if [ ! -f "/storage/coffee_beans" ]; then
        log_error "Coffee beans not found"
        return 1
    fi
    
    if [ ! -f "/storage/water" ]; then
        log_error "Water not available"
        return 1
    fi
    
    log_success "All resources available"
    return 0
}

validate_input() {
    if [ "$CUPS" -lt 1 ] || [ "$CUPS" -gt 10 ]; then
        log_error "Cups must be between 1 and 10"
        return 1
    fi
    log_success "Input validated: $CUPS cup(s)"
    return 0
}

# ============================================================================
# Step Functions - one function per logical step
# ============================================================================

check_prerequisites() {
    log_step "STEP 1: Checking prerequisites"
    
    if ! validate_input; then
        return 1
    fi
    
    if ! require_resources; then
        return 1
    fi
}

prepare_cups() {
    log_step "STEP 2: Preparing cups"
    
    for i in $(seq 1 "$CUPS"); do
        echo "  Preparing cup $i of $CUPS..."
    done
    
    log_success "Cups prepared"
}

grind_and_brew() {
    log_step "STEP 3: Grinding beans and brewing"
    
    local brew_time=0
    
    for i in $(seq 1 "$CUPS"); do
        echo "  Processing cup $i..."
        echo "    - Grinding $COFFEE_TYPE beans..."
        sleep 1
        echo "    - Brewing at ${WATER_TEMP}°C..."
        sleep 2
        brew_time=$((brew_time + 3))
    done
    
    echo "  Total brew time: ${brew_time}s"
    log_success "Brewing complete"
}

serve_coffee() {
    log_step "STEP 4: Serving coffee"
    
    if [ "$CUPS" -eq 1 ]; then
        echo "  Serving 1 cup of fresh $COFFEE_TYPE coffee..."
    else
        echo "  Serving $CUPS cups of fresh $COFFEE_TYPE coffee..."
    fi
    
    log_success "Coffee served! Enjoy!"
}

# ============================================================================
# Main Orchestration
# ============================================================================

main() {
    echo "=========================================="
    echo "Coffee Maker - Intermediate Edition"
    echo "=========================================="
    echo ""
    
    # Execute steps in sequence
    if check_prerequisites && \
       prepare_cups && \
       grind_and_brew && \
       serve_coffee; then
        echo ""
        echo "=========================================="
        log_success "All steps completed successfully!"
        echo "=========================================="
        return 0
    else
        log_error "Script failed at one of the steps"
        return 1
    fi
}

# Execute main function
main "$@"
