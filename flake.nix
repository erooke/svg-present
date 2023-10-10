{
  description = "Bad code to make slides from svg";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
  };

  outputs = {
    self,
    nixpkgs,
  }: let
    system = "x86_64-linux";
    pkgs = nixpkgs.legacyPackages.${system};
    python = pkgs.python311;
    pythonPkgs = pkgs.python311Packages;
    deps = [pkgs.ghostscript pkgs.inkscape];

    svg-present = pythonPkgs.buildPythonPackage {
      pname = "svg-present";
      version = "0.1.0";
      format = "pyproject";
      src = ./.;

      propagatedBuildInputs = deps;

      buildInputs = [pythonPkgs.hatchling];
    };
  in {
    formatter.${system} = pkgs.alejandra;

    packages.${system}.default = svg-present;

    apps.${system}.default = {
      type = "app";
      program = "${svg-present}/bin/mk_pdf";
    };

    devShells.${system}.default = pkgs.mkShell {
      buildInputs = with pkgs; [black isort rye] ++ deps;
    };
  };
}
