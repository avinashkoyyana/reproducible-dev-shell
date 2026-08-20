#!/usr/bin/env bash
set -Eeuo pipefail

THEME_SOURCE="${1:-}"
CONFIG_ROOT="$HOME/.config/repro-dev-shell"
ZSH_CUSTOM_ROOT="$HOME/.oh-my-zsh/custom"
TEMP_FILES=()

info() { printf '\033[1;36m%s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m%s\033[0m\n' "$*" >&2; }
die() { printf '\033[1;31m%s\033[0m\n' "$*" >&2; exit 1; }
cleanup() { ((${#TEMP_FILES[@]} == 0)) || rm -f "${TEMP_FILES[@]}"; }
trap cleanup EXIT

[[ "${EUID}" -ne 0 ]] || die 'Run this script as the normal WSL user, not root.'
command -v sudo >/dev/null || die 'sudo is required.'
sudo -v

info 'Installing Ubuntu development packages...'
sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
  bat ca-certificates curl direnv fd-find fzf git jq ripgrep unzip zsh

for package in eza shellcheck zoxide; do
  if apt-cache show "$package" >/dev/null 2>&1; then
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y "$package"
  else
    warn "Optional apt package is unavailable: $package"
  fi
done

mkdir -p "$HOME/.local/bin" "$CONFIG_ROOT"
ln -sfn "$(command -v fdfind)" "$HOME/.local/bin/fd"
ln -sfn "$(command -v batcat)" "$HOME/.local/bin/bat"

ensure_repo() {
  local url="$1"
  local destination="$2"
  if [[ -d "$destination/.git" ]]; then
    git -C "$destination" pull --ff-only || warn "Could not update $destination; local changes may exist."
  elif [[ -e "$destination" ]]; then
    warn "Skipping $destination because it exists and is not a Git checkout."
  else
    git clone --depth 1 "$url" "$destination"
  fi
}

ensure_repo https://github.com/ohmyzsh/ohmyzsh.git "$HOME/.oh-my-zsh"
ensure_repo https://github.com/zsh-users/zsh-autosuggestions.git "$ZSH_CUSTOM_ROOT/plugins/zsh-autosuggestions"
ensure_repo https://github.com/zsh-users/zsh-syntax-highlighting.git "$ZSH_CUSTOM_ROOT/plugins/zsh-syntax-highlighting"
ensure_repo https://github.com/Aloxaf/fzf-tab.git "$ZSH_CUSTOM_ROOT/plugins/fzf-tab"

if ! command -v oh-my-posh >/dev/null 2>&1; then
  info 'Installing Oh My Posh...'
  installer="$(mktemp)"
  TEMP_FILES+=("$installer")
  curl -fsSL https://ohmyposh.dev/install.sh -o "$installer"
  bash "$installer" -d "$HOME/.local/bin"
fi

if ! command -v uv >/dev/null 2>&1; then
  info 'Installing uv...'
  installer="$(mktemp)"
  TEMP_FILES+=("$installer")
  curl -LsSf https://astral.sh/uv/install.sh -o "$installer"
  sh "$installer"
fi

if [[ -n "$THEME_SOURCE" && -f "$THEME_SOURCE" ]]; then
  cp "$THEME_SOURCE" "$CONFIG_ROOT/oh-my-posh.omp.json"
else
  warn 'Prompt theme source was not found; keeping any existing theme.'
fi

managed_block() {
  local target="$1"
  local name="$2"
  local content_file="$3"
  local begin="# >>> $name >>>"
  local end="# <<< $name <<<"
  local temporary
  temporary="$(mktemp)"

  [[ -f "$target" ]] || touch "$target"
  awk -v begin="$begin" -v end="$end" '
    $0 == begin { skipping = 1; next }
    $0 == end { skipping = 0; next }
    !skipping { print }
  ' "$target" > "$temporary"

  while [[ -s "$temporary" ]] && [[ "$(tail -c 1 "$temporary" | wc -l)" -eq 0 ]]; do
    printf '\n' >> "$temporary"
  done
  printf '\n%s\n' "$begin" >> "$temporary"
  cat "$content_file" >> "$temporary"
  printf '\n%s\n' "$end" >> "$temporary"
  mv "$temporary" "$target"
}

zsh_block="$(mktemp)"
TEMP_FILES+=("$zsh_block")
cat > "$zsh_block" <<'ZSH'
export PATH="$HOME/.local/bin:$PATH"
export ZSH="$HOME/.oh-my-zsh"
ZSH_THEME=""
plugins=(git fzf-tab zsh-autosuggestions zsh-syntax-highlighting)
source "$ZSH/oh-my-zsh.sh"

export FZF_DEFAULT_OPTS='--height 45% --layout=reverse --border --info=inline'
export FZF_DEFAULT_COMMAND='fd --type f --hidden --exclude .git'

[[ -f /usr/share/doc/fzf/examples/key-bindings.zsh ]] && source /usr/share/doc/fzf/examples/key-bindings.zsh
command -v direnv >/dev/null && eval "$(direnv hook zsh)"
command -v zoxide >/dev/null && eval "$(zoxide init zsh)"
command -v oh-my-posh >/dev/null && eval "$(oh-my-posh init zsh --config "$HOME/.config/repro-dev-shell/oh-my-posh.omp.json")"

alias ll='ls -lah'
alias cat='bat'
alias fd='fdfind'
ZSH

if [[ -f "$HOME/.zshrc" && ! -f "$HOME/.zshrc.pre-repro-dev-shell" ]]; then
  cp "$HOME/.zshrc" "$HOME/.zshrc.pre-repro-dev-shell"
fi
managed_block "$HOME/.zshrc" 'reproducible-dev-shell' "$zsh_block"

zsh_path="$(command -v zsh)"
if [[ "${SHELL:-}" != "$zsh_path" ]]; then
  info 'Setting Zsh as the default WSL shell...'
  sudo chsh -s "$zsh_path" "$USER"
fi

info 'WSL/Zsh setup complete. Close this terminal and open the distro again.'
