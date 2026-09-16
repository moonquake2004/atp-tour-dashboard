#!/usr/bin/env python3
"""
Check every internal link and asset reference in the generated site.

1,700+ pages are produced from templates, so a single mistake in a link builder
would break hundreds of pages at once.  This walks the output, extracts every
`href`/`src` that points at a local file and verifies the target exists.

    python3 pyscripts/check_links.py
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlsplit

from wtalib import ROOT

DOCS = ROOT / "docs"

# Attribute values we care about, and the anchors that are intentional no-ops.
HREF = re.compile(r'(?:href|src)="([^"]+)"')
SKIP_SCHEMES = ("http://", "https://", "mailto:", "data:", "javascript:", "//")

# Strings that belong to the companion dashboard and must never appear here.
# Kept as a list so each project can name the other's branding.
FORBIDDEN = ["女子网球", "WTA TOUR", "wtatennis", "wta-tour-dashboard",
             "WTA Tour Dashboard", "WTA 年终"]


def main() -> int:
    if not DOCS.exists():
        raise SystemExit("docs/ is missing — run build_site.py first")

    pages = sorted(DOCS.glob("*.html"))
    print(f"\n▶ Checking links across {len(pages)} pages\n")

    missing: Counter[str] = Counter()
    examples: dict[str, str] = {}
    local_refs = 0
    anchors = 0
    external = 0
    checked = 0

    for page in pages:
        checked += 1
        text = page.read_text(encoding="utf-8")
        for raw in HREF.findall(text):
            if raw.startswith(SKIP_SCHEMES):
                external += 1
                continue
            if raw.startswith("#"):
                anchors += 1
                continue

            target = unquote(urlsplit(raw).path)
            if not target:
                anchors += 1
                continue

            local_refs += 1
            resolved = (page.parent / target).resolve()
            if not resolved.exists():
                missing[target] += 1
                examples.setdefault(target, page.name)

    print(f"  页面        {checked}")
    print(f"  本地引用    {local_refs}")
    print(f"  页内锚点    {anchors}")
    print(f"  外部链接    {external}")

    if missing:
        print(f"\n  ✗ {len(missing)} 个目标缺失（按出现次数排序）:")
        for target, count in missing.most_common(15):
            print(f"      {target}  ×{count}   例如 {examples[target]}")
        return 1

    print("\n  ✓ 全部本地链接与资源引用均存在")

    # A second, cheap sanity check: every page must carry a stylesheet and a title.
    no_title = [p.name for p in pages if "<title>" not in p.read_text(encoding="utf-8")]
    no_css = [p.name for p in pages if "assets/css/style.css" not in p.read_text(encoding="utf-8")]
    if no_title:
        print(f"  ✗ {len(no_title)} 个页面缺少 <title>: {no_title[:5]}")
        return 1
    if no_css:
        print(f"  ✗ {len(no_css)} 个页面未引用样式表: {no_css[:5]}")
        return 1
    print(f"  ✓ 全部页面都含 <title> 与样式表引用")

    empties = [p.name for p in pages if len(p.read_text(encoding="utf-8")) < 2000]
    if empties:
        print(f"  ⚠ {len(empties)} 个页面异常小: {empties[:5]}")

    # Brand guard.  These templates are shared with the companion WTA dashboard,
    # so a stray reference to the wrong tour is easy to introduce and, because it
    # lives in the page shell, would silently appear on every page at once.
    for bad in FORBIDDEN:
        hits = [p.name for p in pages if bad in p.read_text(encoding="utf-8")]
        if hits:
            print(f"  ✗ {len(hits)} 个页面含 «{bad}»（本应只属于另一个站点）: {hits[:3]}")
            return 1
    for asset in list((DOCS / "assets").rglob("*")):
        if asset.is_file() and asset.suffix in (".css", ".js"):
            text = asset.read_text(encoding="utf-8", errors="replace")
            for bad in FORBIDDEN:
                if bad in text:
                    print(f"  ✗ 资源 {asset.name} 含 «{bad}»")
                    return 1
    print(f"  ✓ 品牌一致（未出现 {len(FORBIDDEN)} 个禁词）")

    print(f"\n✓ All {len(pages)} pages checked.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
