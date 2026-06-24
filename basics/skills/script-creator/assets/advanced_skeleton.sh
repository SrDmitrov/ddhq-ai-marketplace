#!/bin/bash

################################################################################
# Advanced Production Script - Skeleton Template
# For team automation at production scale (CSV import, rollbacks, etc.)
# AGENT_IMPLEMENT: Fill in business logic while keeping the structure
################################################################################

set -euo pipefail

# ============================================================================
# Colors for output
# ============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'  # No Color

# ============================================================================
# Configuration
# ============================================================================

# AGENT_IMPLEMENT: Define script-specific configuration variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="/tmp/backup_$(date +%s)"
LOG_DIR="/var/log/your-script"
LOG_FILE="$LOG_DIR/run_$(date +%Y%m%d_%H%M%S).log"

# State tracking - track what operations have been completed (for rollback)
# AGENT_IMPLEMENT: Add state tracking variables specific to your task
STEP_ONE_DONE=false
STEP_TWO_DONE=false
CRITICAL_OPERATION_DONE=false

# ============================================================================
# Utility Functions - Colored Logging
# ============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $*" | tee -a "$LOG_FILE"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $*" | tee -a "$LOG_FILE"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $*" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*" | tee -a "$LOG_FILE"
}

# ============================================================================
# Setup and Cleanup
# ============================================================================

setup_logging() {
    mkdir -p "$LOG_DIR"
    touch "$LOG_FILE"
    log_info "Logging to: $LOG_FILE"
}

# AGENT_IMPLEMENT: Implement cleanup on failure
cleanup() {
    local exit_code=$?
    
    if [ $exit_code -ne 0 ]; then
        log_error "Script failed! Rolling back..."
        rollback_changes
    fi
    
    exit $exit_code
}

trap cleanup EXIT

# AGENT_IMPLEMENT: Implement rollback logic specific to your task
rollback_changes() {
    log_warning "Rolling back changes..."
    
    # Example rollback pattern:
    if [ "$STEP_ONE_DONE" = true ]; then
        log_info "Rolling back step one..."
        # AGENT_IMPLEMENT: Add step-specific rollback logic
    fi
    
    if [ "$CRITICAL_OPERATION_DONE" = true ]; then
        log_info "Rolling back critical operation..."
        # AGENT_IMPLEMENT: Add critical operation rollback (e.g., undo changes)
    fi
    
    if [ -d "$BACKUP_DIR" ]; then
        log_info "Restoring from backup..."
        # AGENT_IMPLEMENT: Restore backups created before critical operations
    fi
    
    log_success "Rollback completed"
}

# ============================================================================
# Prerequisite Validation
# ============================================================================

verify_root() {
    if [ "$EUID" -ne 0 ]; then
        log_error "This script must be run as root"
        exit 1
    fi
}

# AGENT_IMPLEMENT: Implement resource/prerequisite verification
verify_prerequisites() {
    log_info "Step 0/X: Verifying prerequisites..."
    echo ""
    
    # AGENT_IMPLEMENT: Check all required resources exist
    # log_success "Found: /path/to/resource"
    
    # AGENT_IMPLEMENT: Backup critical files before modification
    # mkdir -p "$BACKUP_DIR"
    # cp /important/file "$BACKUP_DIR/"
    # log_info "Backed up critical files"
    
    log_success "All prerequisites verified"
    echo ""
    return 0
}

# AGENT_IMPLEMENT: Implement input validation specific to your task
validate_input() {
    log_info "Validating input..."
    
    # AGENT_IMPLEMENT: Add input validation logic
    # AGENT_IMPLEMENT: Check parameters are within acceptable ranges
    
    log_success "Input validation passed"
    return 0
}

# ============================================================================
# Step Functions - Each step tracked for rollback
# ============================================================================

# AGENT_IMPLEMENT: Implement first step with state tracking
step_one() {
    log_info "Step 1/X: Doing first task..."
    echo ""
    
    # AGENT_IMPLEMENT: Add your business logic here
    # AGENT_IMPLEMENT: Remember to set state variable when step completes
    STEP_ONE_DONE=true
    
    log_success "Step one completed"
    echo ""
}

# AGENT_IMPLEMENT: Implement second step with state tracking
step_two() {
    log_info "Step 2/X: Doing second task..."
    echo ""
    
    # AGENT_IMPLEMENT: Add your business logic here
    # AGENT_IMPLEMENT: Consider using loops for batch operations
    # for item in $(seq 1 10); do
    #     log_info "Processing item $item..."
    # done
    
    STEP_TWO_DONE=true
    
    log_success "Step two completed"
    echo ""
}

# AGENT_IMPLEMENT: Implement critical operation with comprehensive rollback
critical_operation() {
    log_info "Step 3/X: Performing critical operation..."
    echo ""
    
    # AGENT_IMPLEMENT: Ask for user confirmation before critical operations
    # read -p "Proceed with critical operation? (y/n): " -r response
    # if [[ ! $response =~ ^[Yy]$ ]]; then
    #     log_warning "Operation cancelled by user"
    #     return 1
    # fi
    
    # AGENT_IMPLEMENT: Add critical business logic
    # This should be the operation that absolutely needs rollback capability
    
    CRITICAL_OPERATION_DONE=true
    
    log_success "Critical operation completed"
    echo ""
}

# AGENT_IMPLEMENT: Implement final step/verification
finalize() {
    log_info "Step 4/X: Verifying completion..."
    echo ""
    
    # AGENT_IMPLEMENT: Add verification logic
    
    log_success "Verification complete"
    echo ""
}

# ============================================================================
# Main Execution Flow
# ============================================================================

main() {
    setup_logging
    verify_root
    
    log_info "================================================"
    log_info "AGENT_IMPLEMENT: Your Script Title"
    log_info "Target: Production Automation"
    log_info "================================================"
    echo ""
    
    # Execute validation steps
    if ! verify_prerequisites; then
        log_error "Prerequisite verification failed"
        return 1
    fi
    
    if ! validate_input; then
        log_error "Input validation failed"
        return 1
    fi
    
    # Execute main steps in sequence
    if step_one && \
       step_two && \
       critical_operation && \
       finalize; then
        echo ""
        log_success "========================================"
        log_success "All steps completed successfully!"
        log_success "========================================"
        log_info "Log file: $LOG_FILE"
        echo ""
        return 0
    else
        log_error "Script failed"
        log_info "Log file: $LOG_FILE"
        return 1
    fi
}

# Execute main function
main "$@"
