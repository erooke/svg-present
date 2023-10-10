import copy
import logging
import os
from multiprocessing import Pool
from pathlib import Path
from subprocess import DEVNULL, run
from typing import Iterator, Literal
from xml.etree import ElementTree

from .args import parse_args


def main() -> None:
    """
    Renders a pdf slideshow from a single svg.
    This process happens in three steps:
        0. Parse user input
        1. Split the svg into one svg file per slide
        2. Use inkscape to render each of these svgs to pdfs
        3. Combine each pdf into one master pdf
    """
    presentation = Tree()

    args = parse_args()

    level = logging.INFO if args.verbose else logging.WARNING
    logging.basicConfig(level=level, format="%(levelname)s\t%(message)s")

    for file in find_svgs(args.files):
        logging.info(f"loading {file}")
        sub_presentation = load_presentation(file)
        presentation.children.append(sub_presentation)

    pool = Pool(args.threads)

    # Split the slides, start the rendering pool
    print("\r  Splitting Slides", end="")

    os.makedirs(args.cache, exist_ok=True)
    directory = Path(args.cache)

    for count, _ in enumerate(presentation):
        svg = directory / (str(count) + ".svg")
        pdf = directory / (str(count) + ".pdf")
        change = presentation.write(svg)

        if change:
            pool.apply_async(run, (["inkscape", "-o", pdf, svg],), dict(stderr=DEVNULL))

    print("\r✓ Splitting Slides")

    print("  Rendering Slides", end="")
    pool.close()
    pool.join()
    print("\r✓ Rendering Slides")

    print("  Merging slides", end="")
    merge_slides(args.out_format, args.cache, args.output)
    print("\r✓ Merging slides")


def merge_slides(out_format: Literal["pdf", "html"], cache_dir: Path, out_file: Path):
    if out_format == "pdf":
        return merge_pdf(cache_dir, out_file)

    if out_format == "html":
        return merge_html(cache_dir, out_file)

    raise ValueError(f"unknown {out_format=}")


def merge_pdf(cache_dir: Path, out_file: Path):
    merge_cmd = [
        "gs",
        "-dBATCH",
        "-dNOPAUSE",
        "-q",
        "-sDEVICE=pdfwrite",
        "-sOutputFile=" + str(out_file),
    ] + [
        str(file)
        for file in sorted(
            cache_dir.glob("*.pdf"),
            key=lambda x: int(
                x.name.split(".")[0],
            ),
        )
    ]
    run(merge_cmd)


def merge_html(cache_dir: Path, out_file: Path):
    with out_file.open("wb") as f:
        for i, file in enumerate(
            sorted(cache_dir.glob("*.svg"), key=lambda x: int(x.name.split(".")[0]))
        ):
            tree = ElementTree.parse(file)
            root = tree.getroot()
            root.set("id", f"slide-{i}")
            root.set("width", "100%")
            root.set("height", "100%")
            tree.write(f)


def inkscape(name: str) -> str:
    """Add the inkscape namespace to a name"""
    return "{http://www.inkscape.org/namespaces/inkscape}" + name


class Tree:
    def __init__(self, element: ElementTree.Element | None = None) -> None:
        self.children: list[Tree] = []
        self.element: ElementTree.Element | None = element
        self.tree: ElementTree.ElementTree | None = None
        self._visible: bool = False

    def write(self, path: Path) -> bool:
        for child in self.children:
            if child.visible and child.tree:
                tree = copy.deepcopy(child.tree)
                root = tree.getroot()

                for parent in root.findall(".//*[@style='display:none'].."):
                    for node in parent.findall(".*[@style='display:none']"):
                        parent.remove(node)

                if path.exists():
                    old = ElementTree.parse(path).getroot()

                    # This should be good enough for us.
                    # If this is true they are definetly the same etree, it may
                    # miss some equivalent trees
                    if ElementTree.tostring(old) == ElementTree.tostring(root):
                        return False

                tree.write(path)
                return True

        return False

    @property
    def visible(self):
        return self._visible

    @visible.setter
    def visible(self, value: bool) -> None:
        self._visible = value

        if self.element:
            if value:
                self.element.set("style", "display:inline")
            else:
                self.element.set("style", "display:none")

    def __iter__(self):
        self.visible = True

        if not self.children:
            yield self

        for child in self.children:
            yield from child

        self.visible = False


def layer(element: ElementTree.Element) -> Tree | None:
    if element.get(inkscape("groupmode")) != "layer":
        return None

    label = element.get(inkscape("label"))

    if label is None:
        return None

    if label[0] == "(" and label[-1] == ")":
        return None

    tree = Tree(element)
    tree.visible = False

    for child in element:
        if subtree := layer(child):
            tree.children.append(subtree)

    return tree


def load_presentation(file: Path) -> Tree:
    """Load a presentation from an svg file on disk"""
    tree = ElementTree.parse(file)
    ElementTree.register_namespace("svg", "http://www.w3.org/2000/svg")
    root = tree.getroot()
    try:
        root.remove(
            root.findall(".{http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd}*")[0]
        )
    except IndexError:
        pass

    try:
        root.remove(root.findall(".{http://www.w3.org/2000/svg}metadata")[0])
    except IndexError:
        pass

    ns = {"xlink": "http://www.w3.org/1999/xlink", "svg": "http://www.w3.org/2000/svg"}

    symbol = f"{{{ns['svg']}}}symbol"
    group = f"{{{ns['svg']}}}g"

    for prefix, uri in ns.items():
        ElementTree.register_namespace(prefix, uri)

    # Record all the parents of our tree
    parent_map = {c: p for p in tree.iter() for c in p}

    for x in root.findall(".//svg:use", ns):
        # Get what we're linked to
        xlink = ns["xlink"]
        href = x.attrib[f"{{{xlink}}}href"]
        link_target = root.find(f".//*[@id='{href[1:]}']")

        if link_target is None:
            logging.info("There is a dead link in this document")
            continue

        # Find our parent
        parent = parent_map[x]
        index = parent[0:].index(x)

        parent.remove(x)

        # Undo the link by copying it, and transforming it where it needs to go
        new_node = copy.deepcopy(link_target)

        transform = [x.attrib.get("transform")]

        if "x" in x.attrib or "y" in x.attrib:
            x_coord = x.attrib.get("x", 0)
            y_coord = x.attrib.get("y", 0)
            transform.append("translate({},{})".format(x_coord, y_coord))

        transform.append(new_node.attrib.get("transform"))

        transform = [t for t in transform if t is not None]

        new_node.attrib["transform"] = " ".join(transform)

        # We need to merge the styles of the use element and the target element
        # prerference is given to the link target according to mdn
        # https://developer.mozilla.org/en-US/docs/Web/SVG/Element/use
        use_css = x.attrib.get("style", "")
        target_css = link_target.get("style", "")

        use_css = css_to_dict(use_css)
        target_css = css_to_dict(target_css)

        use_css.update(target_css)
        new_node.attrib["style"] = dict_to_css(use_css)

        # Symbols only make sense if they're being referenced
        # if we run into a symbol while dereferencing we need to convert it to a group
        # https://developer.mozilla.org/en-US/docs/Web/SVG/Element/symbol
        if new_node.tag == symbol:
            logging.info(f"Converting element {index} from symbol to group")
            new_node.tag = group

        parent.insert(index, new_node)

    slides = Tree()
    slides.tree = tree
    for child in root:
        if sub_slides := layer(child):
            slides.children.append(sub_slides)

    return slides


def find_svgs(names: list[Path]) -> Iterator[Path]:
    stack = names

    while stack:
        path = stack.pop()

        if path.is_file() and path.suffix == ".svg":
            yield path
            continue

        if path.is_dir():
            stack.extend(sorted(list(path.iterdir()), reverse=True))
            continue


def css_to_dict(css: str) -> dict[str, str]:
    if css == "":
        return dict()

    result = dict()
    for entry in css.split(";"):
        key, value = [part.strip() for part in entry.split(":")]
        result[key] = value
    return result


def dict_to_css(d: dict[str, str]) -> str:
    css = []
    for key, value in d.items():
        css.append(f"{key}: {value}")

    return "; ".join(css)


if __name__ == "__main__":
    main()
