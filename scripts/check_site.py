#!/usr/bin/env python3
"""Check generated pages for missing local links, images, and unresolved Liquid."""
from html.parser import HTMLParser
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlparse


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.ids = []

    def handle_starttag(self, tag, attributes):
        attributes = dict(attributes)
        if attributes.get("id"):
            self.ids.append(attributes["id"])
        for key in ("href", "src"):
            if attributes.get(key):
                self.links.append(attributes[key])


def check(destination):
    root = destination.resolve()
    errors = []
    pages = sorted(root.rglob("*.html"))
    parsed = {}
    for page in pages:
        text = page.read_text(errors="replace")
        if re.search(r"\{%\s*(?:include|assign|for|if|endif)|\{\{\s*(?:site|page|content)\b", text):
            errors.append(f"Unresolved Liquid in {page.relative_to(root)}")
        parser = Links()
        parser.feed(text)
        parsed[page] = parser
        if len(parser.ids) != len(set(parser.ids)):
            errors.append(f"Duplicate HTML id in {page.relative_to(root)}")
    for page, parser in parsed.items():
        for link in parser.links:
            url = urlparse(link)
            if url.scheme in {"mailto", "tel", "data"} or url.netloc and url.netloc != "ijmadrid.github.io":
                continue
            if url.path:
                target = root / unquote(url.path).lstrip("/") if url.path.startswith("/") or url.netloc else page.parent / unquote(url.path)
            else:
                target = page
            if target.is_dir():
                target /= "index.html"
            if not target.exists():
                errors.append(f"{page.relative_to(root)} → missing {link}")
            elif url.fragment and target.resolve() in parsed and unquote(url.fragment) not in parsed[target.resolve()].ids:
                errors.append(f"{page.relative_to(root)} → missing anchor {link}")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        raise SystemExit(1)
    print(f"Checked {len(pages)} HTML pages: local links, images, anchors and Liquid output pass.")


if __name__ == "__main__":
    check(Path(sys.argv[1] if len(sys.argv) > 1 else "_site"))
