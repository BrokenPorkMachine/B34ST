_fbr34ker_complete() {
    local current previous commands profiles
    COMPREPLY=()
    current=${COMP_WORDS[COMP_CWORD]}
    previous=${COMP_WORDS[COMP_CWORD-1]}
    commands='version doctor build test run clean package gate permissions deploy recover inspect evidence boot-image irecovery bringup device bridge session crash trace hardware physical-validation evidence-compare module new-board new-driver new-module new-transport abi-check verify-release compare-releases'
    profiles='direct generic probe'
    if [ "$COMP_CWORD" -eq 1 ]; then
        COMPREPLY=( $(compgen -W "$commands --json --help" -- "$current") )
    elif [ "$previous" = run ]; then
        COMPREPLY=( $(compgen -W "$profiles" -- "$current") )
    elif [ "$previous" = build ] || [ "$previous" = test ]; then
        COMPREPLY=( $(compgen -W '--jobs --qemu --help' -- "$current") )
    else
        COMPREPLY=( $(compgen -f -- "$current") )
    fi
}
complete -F _fbr34ker_complete fbr34ker
