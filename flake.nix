{
  description = "fzf-popup — standalone Bash application";
  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
  };
  outputs =
    { self, nixpkgs, ... }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];
      eachSystem = nixpkgs.lib.genAttrs systems;
      mkPkgs = system: import nixpkgs { inherit system; };
    in
    {
      packages = eachSystem (
        system:
        let
          pkgs = mkPkgs system;
          package = pkgs.callPackage ./nix/package.nix { };
        in
        {
          default = package;
          fzf-popup = package;
        }
      );
      apps = eachSystem (system: {
        default = {
          type = "app";
          program = "${self.packages.${system}.default}/bin/fzf-popup";
        };
        fzf-popup = self.apps.${system}.default;
      });

      formatter = eachSystem (system: (mkPkgs system).nixfmt);
      devShells = eachSystem (
        system:
        let
          pkgs = mkPkgs system;
        in
        {
          default = pkgs.mkShell {
            packages = with pkgs; [
              bash
              coreutils
              fzf
              shellcheck
              nixfmt
            ];
          };
        }
      );
      # Building writeShellApplication already checks Bash syntax and ShellCheck.
      checks = eachSystem (system: {
        default = self.packages.${system}.default;
      });
    };
}
