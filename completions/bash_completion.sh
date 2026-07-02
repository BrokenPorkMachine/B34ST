#!/bin/bash
# SPDX-License-Identifier: BSD-2-Clause
# Bash completion for B34ST entry points

# scripts/B34ST direct subcommands
_b34st_completion() {
    local cur prev
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    # Complete subcommands for scripts/B34ST
    if [[ ${COMP_CWORD} -eq 1 ]]; then
        COMPREPLY=($(compgen -W "build-and-validate run-exploit-chain collect-evidence session info --help -h" -- "${cur}"))
    elif [[ ${prev} == "collect-evidence" ]]; then
        COMPREPLY=($(compgen -W "system.version system.doctor device.detect device.exploit usbliter8.jailbreak ipsw.catalog ipsw.download boot-image.build forensics.acquire --list-operations" -- "${cur}"))
    elif [[ ${prev} == "session" ]]; then
        COMPREPLY=($(compgen -W "info logs" -- "${cur}"))
    fi
}

complete -F _b34st_completion B34ST

# automate.sh subcommands
_automate_completion() {
    local cur prev
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    if [[ ${COMP_CWORD} -eq 1 ]]; then
        COMPREPLY=($(compgen -W "build-and-validate run-exploit-chain collect-evidence session info --help -h" -- "${cur}"))
    elif [[ ${prev} == "collect-evidence" ]]; then
        COMPREPLY=($(compgen -W "system.version system.doctor device.detect device.exploit usbliter8.jailbreak ipsw.catalog ipsw.download boot-image.build forensics.acquire --list-operations" -- "${cur}"))
    elif [[ ${prev} == "session" ]]; then
        COMPREPLY=($(compgen -W "info logs" -- "${cur}"))
    fi
}

complete -F _automate_completion automate