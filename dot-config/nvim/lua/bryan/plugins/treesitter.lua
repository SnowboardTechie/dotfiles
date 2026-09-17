-- nvim-treesitter `main` branch is a parser installer + query collection only.
-- Highlighting, folds and injections are provided by Neovim core; indentation
-- still comes from this plugin and is marked experimental upstream.
return {
  'nvim-treesitter/nvim-treesitter',
  branch = 'main',
  lazy = false, -- main does not support lazy-loading
  build = ':TSUpdate',
  config = function()
    require('nvim-treesitter').install({
      'bash', 'css', 'diff', 'git_rebase', 'gitcommit', 'html', 'ini',
      'javascript', 'json', 'lua', 'markdown', 'markdown_inline', 'nix',
      'python', 'ruby', 'scss', 'ssh_config', 'toml', 'tsx', 'typescript',
      'vim', 'vimdoc', 'yaml',
    })

    vim.api.nvim_create_autocmd('FileType', {
      group = vim.api.nvim_create_augroup('bryan_treesitter', { clear = true }),
      callback = function(args)
        -- No parser installed for this filetype: leave it on regexp syntax.
        if not pcall(vim.treesitter.start, args.buf) then
          return
        end
        vim.bo[args.buf].indentexpr = "v:lua.require'nvim-treesitter'.indentexpr()"
      end,
    })
  end,
}
