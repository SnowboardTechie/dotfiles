# NEOVIM CONFIGURATION

## OVERVIEW

Lazy.nvim-managed config using modern Neovim 0.11+ APIs. Nightfly theme. No Mason — LSPs come from Nix.

## STRUCTURE

```
nvim/
├── init.lua                    # Entry: loads core + lazy
├── lua/bryan/
│   ├── core.lua                # Barrel: keymaps + options
│   ├── lazy.lua                # Lazy.nvim bootstrap
│   ├── core/
│   │   ├── options.lua         # vim.opt settings
│   │   ├── keymaps.lua         # Global keybinds (leader = Space)
│   │   └── colors.lua          # Shared Nightfly palette (imported by plugins)
│   └── plugins/
│       ├── init.lua            # Explicit manifest (require per plugin)
│       └── [plugin].lua        # One file per plugin, returns Lazy spec
└── lazy-lock.json              # Plugin version lockfile
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Add plugin | `lua/bryan/plugins/newplugin.lua` | Return Lazy spec, then add `require()` to `plugins/init.lua` |
| Add keybinding | `lua/bryan/core/keymaps.lua` | Or in plugin's config function if plugin-specific |
| Change editor option | `lua/bryan/core/options.lua` | |
| Add LSP server | `lua/bryan/plugins/lsp.lua` | Add to `vim.lsp.enable()` list; server must be on PATH via Nix |
| Change colors | `lua/bryan/core/colors.lua` | Lualine + nvim-tree auto-inherit; also update Alacritty |

## CONVENTIONS

- Each plugin = one file in `plugins/`, returning a Lazy.nvim plugin spec table
- Explicit manifest in `plugins/init.lua` — add a `require()` line for every new plugin
- LSP: uses `vim.lsp.config()` / `vim.lsp.enable()` (0.11+ API), NOT `lspconfig[server].setup()`
- Completion: `blink.cmp` (Rust-accelerated), NOT nvim-cmp
- Colors: import `bryan.core.colors` module — never hardcode hex values in plugin configs
- Leader namespaces: `s`=splits, `t`=tabs, `f`=find/format, `e`=explorer/diagnostic, `h`=hunks, `o`=opencode, `r`=refactor, `c`=code

## ANTI-PATTERNS

| Rule | Reason |
|------|--------|
| No Mason/mason-lspconfig | LSPs managed by Nix. To add one: update nix-configs flake, then add to `vim.lsp.enable()` |
| No hardcoded hex colors in plugins | Use `require("bryan.core.colors")` |
| No `lspconfig[server].setup()` | Use modern `vim.lsp.config()` + `vim.lsp.enable()` API |
| No formatter plugins (conform.nvim) | Formatting via `vim.lsp.buf.format` only (for now) |

## ENABLED LSP SERVERS

`pyright`, `ts_ls`, `lua_ls`, `nixd`, `solargraph`

## PLUGIN STACK (17 plugins)

colorscheme (nightfly), lsp + fidget, blink.cmp, telescope, treesitter, lualine, nvim-tree, bufferline, gitsigns, comment, autopairs, surround, indent-blankline, which-key, vim-maximizer, vim-be-good, opencode
