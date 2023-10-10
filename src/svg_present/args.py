from argparse import ArgumentParser
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass
class Args:
    threads: int
    output: Path
    cache: Path
    verbose: bool
    files: list[Path]
    out_format: Literal["html", "pdf"]


def parse_args() -> Args:
    parser = ArgumentParser(
        prog="mk_pdf",
        description="A python script to create slides using inkscape",
    )

    parser.add_argument(
        "files",
        metavar="file",
        nargs="+",
        help="Inkscape file to use",
        type=Path,
    )

    parser.add_argument(
        "-o",
        "--output",
        metavar="file",
        help="Output for the slideshow",
        nargs="?",
        type=Path,
        default="talk.pdf",
    )

    parser.add_argument(
        "-j",
        "--threads",
        metavar="num",
        help="How many inkscape processess to spawn",
        nargs="?",
        type=int,
        default=None,
    )

    parser.add_argument(
        "--cache",
        help="Where to cache files",
        nargs="?",
        type=Path,
        metavar="dir",
        default="talk_cache",
    )

    parser.add_argument(
        "--format",
        help="output format",
        default="pdf",
        metavar="format",
        dest="out_format",
        required=False,
    )

    parser.add_argument(
        "-v", "--verbose", help="Print debug information", action="store_true"
    )

    args = parser.parse_args()
    return Args(**vars(args))
