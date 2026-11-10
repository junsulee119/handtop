# Start the labwc desktop on tty1 after auto-login.
# shellcheck shell=sh
# Logging out of labwc returns to getty, which logs in again = session restart.
# Gives up after 3 quick failures per boot and leaves a shell on tty1.
# Let VA-API clients (Chromium, VLC) reach the VPU: the libva driver over the
# V4L2 request API is installed in the image, but libva only looks for it when
# asked by name (there is no default driver on arm64). Exported before labwc
# starts, so every app launched from the desktop inherits it.
export LIBVA_DRIVER_NAME=v4l2_request

if [ "$(tty)" = "/dev/tty1" ] && [ -z "${WAYLAND_DISPLAY:-}" ] && [ -z "${RG_NO_DESKTOP:-}" ]; then
  _rg_count="${XDG_RUNTIME_DIR:-/tmp}/rg35xxh-session-starts"
  _rg_n=$(( $(cat "$_rg_count" 2>/dev/null || echo 0) + 1 ))
  echo "$_rg_n" > "$_rg_count"
  if [ "$_rg_n" -le 3 ]; then
    mkdir -p "$HOME/.local/state"
    # Pointer of the current theme (rg35xxh-theme writes CURSOR_* into theme.env; labwc reads
    # XCURSOR_* only when it starts, so a new theme's cursor shows from the next log-in).
    # Handtop's own until a theme has been rendered.
    _rg_env="${XDG_STATE_HOME:-$HOME/.local/state}/rg35xxh/theme/theme.env"
    XCURSOR_THEME=$(sed -n "s/^CURSOR_THEME='\([A-Za-z0-9 ._+-]*\)'\$/\1/p" "$_rg_env" 2>/dev/null)
    XCURSOR_SIZE=$(sed -n "s/^CURSOR_SIZE='\([0-9]*\)'\$/\1/p" "$_rg_env" 2>/dev/null)
    export XCURSOR_THEME="${XCURSOR_THEME:-Handtop}" XCURSOR_SIZE="${XCURSOR_SIZE:-24}"
    exec labwc > "$HOME/.local/state/labwc.log" 2>&1
  fi
  echo "labwc failed to start 3 times; see ~/.local/state/labwc.log (shell left on tty1)."
fi
