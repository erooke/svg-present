{
  description = "Bad code to make slides from svg";

  outputs = { self, nixpkgs }:
  let
    system = "x86_64-linux";
    pkgs = nixpkgs.legacyPackages.${system};
    deps = with pkgs; [ python310 ghostscript inkscape ];
    mk_pdf = pkgs.stdenv.mkDerivation {
      name = "svg-present";
      src = ./.;
      unpackPhase = "true";
      buildInputs = [ pkgs.makeWrapper ] ++ deps;
      installPhase = ''
        mkdir -p $out/bin
        cp $src/mk_pdf $out/bin/mk_pdf
        wrapProgram $out/bin/mk_pdf \
          --prefix PATH : ${pkgs.lib.makeBinPath deps}
      '';
    };
  in
  {
    packages.${system}.default = mk_pdf;

    apps.${system}.default = {
      type = "app";
      program = "${mk_pdf}/bin/mk_pdf";
    };

    devShells.${system}.default = pkgs.mkShell {
      buildInputs = with pkgs; [ black isort pyright ] ++ deps;
    };
  };
}
