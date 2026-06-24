#!/bin/bash

# Intermediate Coffee Making Script - Skeleton Template
# For seniors automating tasks or creating team tools
# AGENT_IMPLEMENT: Fill in the business logic for each function

set -euo pipefail

# ============================================================================
# Configuration
# ============================================================================

CUPS=${1:-1}
# AGENT_IMPLEMENT: Add more configuration variables as needed
SCRIPT_NAME="$(basename "$0")"

# ============================================================================
# Logging Functions
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

# AGENT_IMPLEMENT: Implement resource checking
require_resources() {
    log_step "Checking resources..."
    # AGENT_IMPLEMENT: Verify all required resources/files exist
    log_success "Resources verified"
    return 0
}

# AGENT_IMPLEMENT: Implement input validation
validate_input() {
    # AGENT_IMPLEMENT: Add input validation logic
    log_success "Input validated"
    return 0
}

# ============================================================================
# Step Functions - Separate logic into functions
# ============================================================================

# AGENT_IMPLEMENT: Implement prerequisites check
check_prerequisites() {
    log_step "STEP 1: Checking prerequisites"
    
    if ! validate_input; then
        return 1
    fi
    
    if ! require_resources; then
        return 1
    fi
}

# AGENT_IMPLEMENT: Implement first main step
step_one() {
    log_step "STEP 2: Doing first action"
    
    # AGENT_IMPLEMENT: Add your logic here
    # Consider using loops for repetitive work:
    # for i in $(seq 1 "$CUPS"); do
    #     echo "  Processing item $i..."
    # done
    
    log_success "Step one completed"
}

# AGENT_IMPLEMENT: Implement second main step
step_two() {
    log_step "STEP 3: Doing second action"
    
    # AGENT_IMPLEMENT: Add your logic here
    
    log_success "Step two completed"
}

# AGENT_IMPLEMENT: Implement final step
finalize() {
    log_step "STEP 4: Finalizing"
    
    # AGENT_IMPLEMENT: Add completion logic here
    
    log_success "All done"
}

# ============================================================================
# Main Orchestration
# ============================================================================

main() {
    echo "=========================================="
    echo "AGENT_IMPLEMENT: Your Script Name"
    echo "=========================================="
    echo ""
    
    # Execute steps in sequence
    if check_prerequisites && \
       step_one && \
       step_two && \
       finalize; then
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
