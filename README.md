# fzf-popup

A Bash selection program with fzf. It accepts candidates on stdin and returns
the original selected rows on stdout. It contains no terminal emulator,
compositor, clipboard or notification-specific code.

```sh
nix run github:SpreadZhao/fzf-popup -- --help
printf '%s\n' one two | fzf-popup -- --prompt='Pick> '
printf '%s\n' one two | fzf-popup --title 'Choose' --launcher ./terminal-adapter -- --multi
```

`--launcher EXECUTABLE` overrides `FZF_POPUP_LAUNCHER`. Without either, fzf runs
in the current terminal. Put all fzf arguments after `--`; they are passed
unchanged, including preview commands, field delimiters and key bindings.
fzf configuration from its usual environment variables is inherited.

The launcher receives a command and its arguments, must execute them without
reinterpreting them as shell text, and must wait until they finish. The title
is available as `FZF_POPUP_TITLE`. For example, a Foot adapter can contain:

```sh
#!/usr/bin/env bash
exec footclient --client-environment -a my-popup -T "$FZF_POPUP_TITLE" -- "$@"
```

Configure your window manager to float windows matching that app-id. Other
terminals work through their own adapters with the same synchronous contract.
The adapter and window rules belong to the desktop configuration, not this package.

Output and exit status come from fzf: 0 selected, 1 no match, 2 error, 130 cancel.
Callers decide what to do after cancellation. A launcher that returns before the
command finishes is unsupported and reported as an error. Launcher diagnostics
go to stderr. Temporary files have private permissions and are removed on exit;
concurrent calls do not share files. Candidate content is never evaluated by the
launcher. As with fzf, preview and action commands are caller-provided shell code.

Nix exports `packages.<system>.default` (also `fzf-popup`), `apps`, `checks`,
`formatter` and `devShells` for x86_64-linux and aarch64-linux. Build with
`nix build`, test with `nix flake check`, and develop with `nix develop`.
Runtime dependencies are Bash, coreutils and fzf.
