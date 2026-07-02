#!/usr/bin/env bash
# SPDX-License-Identifier: BSD-2-Clause
# Unified Automation Helper for B34ST
# Consolidates entry points and streamlines common workflows

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
BIN_ROOT="$(CDPATH= cd -- "${SCRIPT_DIR}/.." && pwd)"

# Detect source root
if [ -z "${FBR34KER_SOURCE_ROOT:-}" ]; then
    if [ -f "$PWD/fbr34ker" ] && [ -d "$PWD/host" ] && [ -f "$PWD/Makefile" ]; then
        FBR34KER_SOURCE_ROOT=$PWD
    elif [ -f "$BIN_ROOT/fbr34ker" ] && [ -d "$BIN_ROOT/host" ] && [ -f "$BIN_ROOT/Makefile" ]; then
        FBR34KER_SOURCE_ROOT=$BIN_ROOT
    else
        FBR34KER_SOURCE_ROOT=$BIN_ROOT/share/fbr34ker
    fi
    export FBR34KER_SOURCE_ROOT
fi

cd "$FBR34KER_SOURCE_ROOT"

# Helper: Print usage
print_help() {
    cat << EOF
USAGE:
    ./automate.sh <command> [options]

Commands:
    interactive                 Launch unified interactive control panel (default)
    run-operation <key> [args]  Run a single operation with evidence collection
    build-and-validate          Build and validate workflow
    run-exploit-chain [args]    Run USBliter8 exploit chain with evidence
    run-guided-workflow [args]  Launch guided research runtime
    collect-evidence <operation> Collect evidence from another tool
    session info                 Print session information
    session logs [operation]    Show session logs

Options:
    --help                      Show this help
    --json                      Output JSON for scripting
    --session-dir <path>        Use specific session directory
EOF
}

# Helper: Run operation with evidence collection
run_operation() {
    local key="$1"
    shift
    local extra_args="$@"

    if [ -z "$key" ]; then
        echo "Error: Operation key required for run-operation"
        exit 1
    fi

    # Map command keys to fbr34ker commands
    local operation_arg="$key"

    # Build command with evidence collection
    local evidence_file="$(date +%Y%m%d-%H%M%S)-${key////-}.json"
    local python_script="$SCRIPT_DIR/run-operation.py"

    if [ -f "$python_script" ]; then
        python3 "$python_script" "$key" "$extra_args" "$evidence_file"
    else
        echo "Error: run-operation.py not found at $python_script"
        exit 1
    fi
}

# Helper: Create build-and-validate workflow
build_and_validate() {
    echo "=== B34ST Build and Validate Workflow ==="

    # Build operational image
    echo "Building operational image..."
    if ! make build-operational; then
        echo "Build failed, exiting"
        exit 1
    fi

    # Run static analysis
    echo "Running static analysis..."
    if [ -f "$BIN_ROOT/scripts/check_sources.py" ]; then
        python3 "$BIN_ROOT/scripts/check_sources.py"
    fi

    # Run release gate
    echo "Running release gate validation..."
    if [ -f "$BIN_ROOT/scripts/release_gate.py" ]; then
        python3 "$BIN_ROOT/scripts/release_gate.py" --post-build
    fi

    echo "=== Build and validate completed ==="
}

# Helper: Run exploit chain with evidence
run_exploit_with_evidence() {
    local extra_args="$@"

    # Run through scripts/B34ST to handle evidence collection
    if [ -f "$SCRIPT_DIR/B34ST" ]; then
        "$SCRIPT_DIR/B34ST" --command device.exploit "$extra_args"
    else
        echo "Error: scripts/B34ST not found at $SCRIPT_DIR/B34ST"
        exit 1
    fi
}

# Helper: Run guided workflow
run_guided_workflow() {
    local extra_args="$@"

    if [ -f "$SCRIPT_DIR/guided_research_runtime.py" ]; then
        python3 "$SCRIPT_DIR/guided_research_runtime.py" guided "$extra_args"
    else
        echo "Error: guided_research_runtime.py not found"
        exit 1
    fi
}

# Helper: Collect evidence from another tool
collect_evidence() {
    local operation="$1"

    if [ -z "$operation" ]; then
        echo "Error: Operation name required for collect-evidence"
        exit 1
    fi

    # Use b34stool.py's evidence collection if available
    local python_script="$SCRIPT_DIR/collect-evidence.py"

    if [ -f "$python_script" ]; then
        python3 "$python_script" "$operation"
    else
        echo "Info: collect-evidence.py not found - using manual method"
        echo "Create evidence file with: FBR34KER_OPERATION=$operation"
        echo "Evidence will be collected in runtime-artifacts/b34st/b34stool/"
    fi
}

# Main entry point
main() {
    local command="${1:-interactive}"
    shift || true

    case "$command" in
        interactive)
            if [ -f "$SCRIPT_DIR/B34ST" ]; then
                exec "$SCRIPT_DIR/B34ST" "$@"
            else
                echo "Error: scripts/B34ST not found at $SCRIPT_DIR/B34ST"
                exit 1
            fi
            ;;

        run-operation)
            run_operation "$@"
            ;;

        build-and-validate)
            build_and_validate
            ;;

        run-exploit-chain)
            run_exploit_with_evidence "$@"
            ;;

        run-guided-workflow)
            run_guided_workflow "$@"
            ;;

        collect-evidence)
            collect_evidence "$@"
            ;;

        session)
            local subcommand="${1:-}"
            case "$subcommand" in
                info)
                    echo "B34ST Session Management"
                    echo "Session directory will be created in runtime-artifacts/b34st/b34stool/"
                    ;;
                logs)
                    local operation="${2:-}"
                    if [ -f "$FBR34KER_SOURCE_ROOT/b34stool.py" ] && [ "$operation" ]; then
                        python3 "$FBR34KER_SOURCE_ROOT/b34stool.py" --session-dir "$FBR34KER_SOURCE_ROOT/runtime-artifacts/b34st/b34stool" session logs "$@"
                    else
                        echo "Session logs not configured"
                    fi
                    ;;
                *)
                    echo "Error: Unknown session subcommand: $subcommand"
                    print_help
                    exit 1
                    ;;
            esac
            ;;

        --help|-h)
            print_help
            ;;

        *)
            echo "Error: Unknown command: $command"
            print_help
            exit 1
            ;;
    esac
}

# Execute main
main "$@"
