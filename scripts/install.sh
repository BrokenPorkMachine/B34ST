#!/usr/bin/env sh
set -eu

usage() {
    cat <<'USAGE'
Usage: scripts/install.sh [--prefix PATH] [--destdir PATH]

Install the B34ST/FBR34KER source tree, command wrappers, manual page, and shell
completions. PREFIX defaults to /usr/local. DESTDIR is intended for package
staging and defaults to empty.
USAGE
}

PREFIX=${PREFIX:-/usr/local}
DESTDIR=${DESTDIR:-}
while [ "$#" -gt 0 ]; do
    case "$1" in
        --prefix) [ "$#" -ge 2 ] || { echo "missing --prefix value" >&2; exit 2; }; PREFIX=$2; shift 2 ;;
        --destdir) [ "$#" -ge 2 ] || { echo "missing --destdir value" >&2; exit 2; }; DESTDIR=$2; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
    esac
done

case "$PREFIX" in /*) ;; *) echo "PREFIX must be absolute" >&2; exit 2 ;; esac
case "$DESTDIR" in ""|/*) ;; *) echo "DESTDIR must be empty or absolute" >&2; exit 2 ;; esac

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
SHARE_DIR="$DESTDIR$PREFIX/share/fbr34ker"
BIN_DIR="$DESTDIR$PREFIX/bin"
MAN_DIR="$DESTDIR$PREFIX/share/man/man1"
BASH_DIR="$DESTDIR$PREFIX/share/bash-completion/completions"
ZSH_DIR="$DESTDIR$PREFIX/share/zsh/site-functions"

for directory in "$SHARE_DIR" "$BIN_DIR" "$MAN_DIR" "$BASH_DIR" "$ZSH_DIR"; do
    mkdir -p "$directory"
done

# Copy the checked source tree without transient build/release outputs.
(
    cd "$ROOT"
    tar -cf - \
        --exclude='./.git' \
        --exclude='./build' --exclude='./build-*' \
        --exclude='./runtime-artifacts' --exclude='./diagnostics' \
        --exclude='./validation-logs' --exclude='./dist' \
        --exclude='./__pycache__' \
        .
) | (
    cd "$SHARE_DIR"
    tar -xf -
)

cat > "$BIN_DIR/fbr34ker" <<'EOF_WRAPPER'
#!/usr/bin/env sh
set -eu
BIN_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
exec python3 "$BIN_ROOT/share/fbr34ker/fbr34ker" "$@"
EOF_WRAPPER
chmod 0755 "$BIN_DIR/fbr34ker"
cat > "$BIN_DIR/B34ST" <<'EOF_WRAPPER'
#!/usr/bin/env sh
set -eu
BIN_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$BIN_ROOT/share/fbr34ker"
exec python3 -m b34st.b34st "$@"
EOF_WRAPPER
chmod 0755 "$BIN_DIR/B34ST"
ln -sf B34ST "$BIN_DIR/b34stctl"
chmod 0755 "$SHARE_DIR/fbr34ker" "$SHARE_DIR"/host/fbr34k* "$SHARE_DIR"/scripts/*.sh "$SHARE_DIR"/scripts/*.py "$SHARE_DIR/scripts/B34ST" 2>/dev/null || true
install -m 0644 "$ROOT/man/fbr34ker.1" "$MAN_DIR/fbr34ker.1"
install -m 0644 "$ROOT/man/B34ST.1" "$MAN_DIR/B34ST.1"
install -m 0644 "$ROOT/completions/fbr34ker.bash" "$BASH_DIR/fbr34ker"
install -m 0644 "$ROOT/completions/_fbr34ker" "$ZSH_DIR/_fbr34ker"

printf 'installed FBR34KER under %s\n' "$DESTDIR$PREFIX"
printf 'run: %s/B34ST\n' "$PREFIX/bin"
