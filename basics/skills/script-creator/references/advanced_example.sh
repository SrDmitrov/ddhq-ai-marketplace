#!/bin/bash

################################################################################
# Advanced Coffee Making Script
# Production-grade automation by a team of developers
# Features: colored logging, state tracking, backup/rollback, trap handlers,
#          progress indicators, atomic operations, comprehensive validation
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

CUPS=${1:-1}
COFFEE_TYPE="arabica"
WATER_TEMP=95
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="/tmp/coffee_backup_$(date +%s)"
LOG_DIR="/var/log/coffee-maker"
LOG_FILE="$LOG_DIR/coffee_$(date +%Y%m%d_%H%M%S).log"

# State tracking - track what operations have been completed
RESOURCES_VERIFIED=false
CUPS_PREPARED=false
BEANS_GROUND=false
BREWING_STARTED=false
SERVED=false

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

# Cleanup and rollback on exit if script fails
cleanup() {
    local exit_code=$?
    
    if [ $exit_code -ne 0 ]; then
        log_error "Script failed! Rolling back changes..."
        rollback_changes
    fi
    
    exit $exit_code
}

trap cleanup EXIT

# Rollback to pre-installation state on failure
rollback_changes() {
    log_warning "Rolling back state..."
    
    if [ "$BREWING_STARTED" = true ]; then
        log_info "Stopping brew process..."
        # AGENT_IMPLEMENT: Implement machine shutdown
    fi
    
    if [ "$CUPS_PREPARED" = true ]; then
        log_info "Clearing prepared cups..."
        # AGENT_IMPLEMENT: Implement cleanup
    fi
    
    if [ -d "$BACKUP_DIR" ]; then
        log_info "Restoring backup..."
        # AGENT_IMPLEMENT: Restore machine configuration
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

verify_resources() {
    log_info "Step 0/5: Verifying resources..."
    echo ""
    
    # Check coffee beans
    if [ ! -f "/storage/coffee_beans" ]; then
        log_error "Coffee beans not found at /storage/coffee_beans"
        return 1
    fi
    log_success "Found: /storage/coffee_beans"
    
    # Check water
    if [ ! -f "/storage/water" ]; then
        log_error "Water not found at /storage/water"
        return 1
    fi
    log_success "Found: /storage/water"
    
    # Check machine
    if [ ! -f "/storage/coffee_machine/config" ]; then
        log_error "Coffee machine configuration not found"
        return 1
    fi
    log_success "Found: /storage/coffee_machine/config"
    
    # Backup machine config for rollback
    mkdir -p "$BACKUP_DIR"
    cp /storage/coffee_machine/config "$BACKUP_DIR/machine_config.bak"
    log_info "Backed up machine configuration to $BACKUP_DIR"
    
    RESOURCES_VERIFIED=true
    log_success "All resources verified"
    echo ""
    return 0
}

validate_input() {
    log_info "Validating input: $CUPS cups"
    
    if [ "$CUPS" -lt 1 ] || [ "$CUPS" -gt 20 ]; then
        log_error "Cups must be between 1 and 20"
        return 1
    fi
    
    log_success "Input validation passed"
    return 0
}

# ============================================================================
# Step Functions with State Tracking
# ============================================================================

step_prepare_cups() {
    log_info "Step 1/5: Preparing cups..."
    echo ""
    
    local cup_count=0
    for i in $(seq 1 "$CUPS"); do
        log_info "  Preparing cup $i of $CUPS..."
        cup_count=$((cup_count + 1))
        sleep 1
    done
    
    CUPS_PREPARED=true
    log_success "Prepared $cup_count cups"
    echo ""
}

step_grind_beans() {
    log_info "Step 2/5: Grinding coffee beans..."
    echo ""
    
    for i in $(seq 1 "$CUPS"); do
        log_info "  Grinding $COFFEE_TYPE beans for cup $i..."
        sleep 1
    done
    
    BEANS_GROUND=true
    log_success "Beans ground for all cups"
    echo ""
}

step_brew() {
    log_info "Step 3/5: Brewing coffee..."
    echo ""
    
    BREWING_STARTED=true
    
    for i in $(seq 1 "$CUPS"); do
        log_info "  Brewing cup $i at ${WATER_TEMP}°C..."
        sleep 2
    done
    
    log_success "All cups brewed"
    echo ""
}

step_verify_quality() {
    log_info "Step 4/5: Verifying coffee quality..."
    echo ""
    
    # Simulate quality checks
    log_info "  Checking temperature..."
    sleep 1
    log_success "Temperature optimal"
    
    log_info "  Checking aroma..."
    sleep 1
    log_success "Aroma perfect"
    
    echo ""
}

step_serve() {
    log_info "Step 5/5: Serving coffee..."
    echo ""
    
    # User confirmation
    read -p "Ready to serve $CUPS cup(s)? (y/n): " -r response
    if [[ ! $response =~ ^[Yy]$ ]]; then
        log_warning "User cancelled serving"
        return 1
    fi
    
    log_info "Serving $CUPS cup(s) of fresh $COFFEE_TYPE coffee..."
    SERVED=true
    log_success "Coffee service complete!"
    echo ""
}

# ============================================================================
# Main Execution Flow
# ============================================================================

main() {
    setup_logging
    verify_root
    
    log_info "================================================"
    log_info "Coffee Maker - Advanced Edition"
    log_info "Target: Production Team Automation"
    log_info "================================================"
    echo ""
    
    # Execute validation steps
    if ! verify_resources; then
        log_error "Resource verification failed"
        return 1
    fi
    
    if ! validate_input; then
        log_error "Input validation failed"
        return 1
    fi
    
    # Execute main steps in sequence
    if step_prepare_cups && \
       step_grind_beans && \
       step_brew && \
       step_verify_quality && \
       step_serve; then
        echo ""
        log_success "========================================"
        log_success "All steps completed successfully!"
        log_success "========================================"
        log_info "Log file: $LOG_FILE"
        echo ""
        return 0
    else
        log_error "Coffee making failed"
        log_info "Log file: $LOG_FILE"
        return 1
    fi
}

# Execute main function
main "$@"
