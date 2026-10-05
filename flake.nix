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
              python3
              shellcheck
              nixfmt
            ];
          };
        }
      );
      checks = eachSystem (
        system:
        let
          pkgs = mkPkgs system;
          passed = true;
        in
        {
          default =
            assert passed;
            pkgs.runCommand "fzf-popup-checks"
              {
                nativeBuildInputs = with pkgs; [
                  bash
                  coreutils
                  fzf
                  python3
                  shellcheck
                  nixfmt
                ];
                application = self.packages.${system}.default;
                REAL_FZF = "${pkgs.fzf}/bin/fzf";

              }
              ''
                cp -R ${./.} source
                chmod -R u+w source

                cd source
                patchShebangs src tests
                export PATH="$PWD/src:$PATH"
                "$application/bin/fzf-popup" --help
                shellcheck src/*
                for file in src/* ; do bash -n "$file"; done
                nixfmt --check flake.nix nix/*.nix
                python3 tests/check.py
                touch "$out"
              '';
        }
      );
    };
}
