{
  writeShellApplication,
  coreutils,
  fzf,
}:
writeShellApplication {
  name = "fzf-popup";
  runtimeInputs = [
    coreutils
    fzf
  ];
  text = builtins.readFile ../src/fzf-popup;
}
