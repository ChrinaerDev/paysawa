"""Builds the documentation: Markdown files in docs/ and the data file of the website (docs_site/assets/content.js).

    python docs_src/build.py

Edit pages in docs_src/pages/*.md and endpoints in docs_src/reference.py, set BASE_URL in docs_src/config.py, then rebuild.
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

import config  # noqa: E402
from reference import ENDPOINTS, GROUP_ORDER  # noqa: E402
from reference_fr import FR  # noqa: E402

BASE = "{{BASE_URL}}"


# ================================================================== markdown -> html (small, dependency free)
def _link(match: re.Match) -> str:
    text, url = match.group(1), match.group(2)
    if url.startswith("#"):
        return f'<a href="{url}">{text}</a>'
    if re.match(r"^(https?://|mailto:)", url):
        return f'<a href="{url}" target="_blank" rel="noopener">{text}</a>'
    return text  # anything else (javascript:, relative files...) is dropped, text kept


def inline(text: str) -> str:
    out = []
    for part in re.split(r"(`[^`]+`)", text):
        if len(part) > 1 and part.startswith("`") and part.endswith("`"):
            out.append("<code>" + html.escape(part[1:-1], quote=False) + "</code>")
            continue
        part = html.escape(part, quote=False)
        part = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", part)
        part = re.sub(r"(?<![\*\w])\*(?!\s)([^*]+?)(?<!\s)\*(?![\*\w])", r"<em>\1</em>", part)
        part = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", _link, part)
        out.append(part)
    return "".join(out)


def code_block(code: str, lang: str) -> str:
    return f'<pre class="code" data-lang="{html.escape(lang or "text")}"><code>{html.escape(code, quote=False)}</code></pre>'


def _split_row(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|") and not line.endswith("\\|"):
        line = line[:-1]
    return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", line)]


def md_to_html(md: str) -> str:
    lines = md.split("\n")
    out: list[str] = []
    i = 0
    block_start = re.compile(r"^(#{1,4} |```|>|\s*[-*] |\s*\d+\. |\||---\s*$)")
    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            lang, buf = line[3:].strip(), []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            out.append(code_block("\n".join(buf), lang))
        elif re.match(r"^#{1,4} ", line):
            level = len(line) - len(line.lstrip("#"))
            out.append(f"<h{level}>{inline(line[level:].strip())}</h{level}>")
            i += 1
        elif line.strip() == "---":
            out.append("<hr>")
            i += 1
        elif line.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:\-|]+\|\s*$", lines[i + 1]):
            head = _split_row(line)
            i += 2
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(_split_row(lines[i]))
                i += 1
            t = "<div class=\"table-wrap\"><table><thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in head) + "</tr></thead><tbody>"
            for r in rows:
                t += "<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>"
            out.append(t + "</tbody></table></div>")
        elif line.startswith(">"):
            buf = []
            while i < len(lines) and lines[i].startswith(">"):
                buf.append(lines[i][1:].strip())
                i += 1
            out.append("<blockquote><p>" + inline(" ".join(buf)) + "</p></blockquote>")
        elif re.match(r"^\s*[-*] ", line):
            items = []
            while i < len(lines) and re.match(r"^\s*[-*] ", lines[i]):
                item = re.sub(r"^\s*[-*] ", "", lines[i])
                i += 1
                while i < len(lines) and lines[i].startswith("  ") and not re.match(r"^\s*[-*] ", lines[i]) and lines[i].strip():
                    item += " " + lines[i].strip()
                    i += 1
                items.append(item)
            out.append("<ul>" + "".join(f"<li>{inline(x)}</li>" for x in items) + "</ul>")
        elif re.match(r"^\s*\d+\. ", line):
            items = []
            while i < len(lines) and re.match(r"^\s*\d+\. ", lines[i]):
                item = re.sub(r"^\s*\d+\. ", "", lines[i])
                i += 1
                while i < len(lines) and lines[i].startswith("   ") and not re.match(r"^\s*\d+\. ", lines[i]) and lines[i].strip():
                    item += " " + lines[i].strip()
                    i += 1
                items.append(item)
            out.append("<ol>" + "".join(f"<li>{inline(x)}</li>" for x in items) + "</ol>")
        elif not line.strip():
            i += 1
        else:
            buf = [line]
            i += 1
            while i < len(lines) and lines[i].strip() and not block_start.match(lines[i]):
                buf.append(lines[i])
                i += 1
            out.append("<p>" + inline(" ".join(s.strip() for s in buf)) + "</p>")
    return "\n".join(out)


def strip_tags(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


# ================================================================== code samples
def py_literal(value, indent: int = 0) -> str:
    pad = "    " * (indent + 1)
    end = "    " * indent
    if isinstance(value, dict):
        if not value:
            return "{}"
        return "{\n" + "".join(f"{pad}{json.dumps(k)}: {py_literal(v, indent + 1)},\n" for k, v in value.items()) + end + "}"
    if isinstance(value, list):
        return "[" + ", ".join(py_literal(v, indent) for v in value) + "]"
    if value is None:
        return "None"
    if value is True:
        return "True"
    if value is False:
        return "False"
    return json.dumps(value, ensure_ascii=False)


def auth_header(ep: dict) -> str | None:
    return {"token": "Authorization: Token YOUR_TOKEN", "apikey": "Authorization: Bearer sk_test_YOUR_KEY"}.get(ep["auth"])


def example_url(ep: dict) -> str:
    path = ep.get("example_path", ep["path"])
    if ep.get("query"):
        path += "?" + "&".join(f"{k}={v}" for k, v in ep["query"].items())
    return BASE + path


def sample_curl(ep: dict) -> str:
    parts = [f'curl {"-X " + ep["method"] + " " if ep["method"] != "GET" else ""}"{example_url(ep)}"']
    header = auth_header(ep)
    if header:
        parts.append(f'-H "{header}"')
    for extra in ep.get("extra_headers", []):
        parts.append(f'-H "{extra}"')
    if ep.get("body"):
        parts.append('-H "Content-Type: application/json"')
        parts.append("-d '" + json.dumps(ep["body"], indent=2, ensure_ascii=False) + "'")
    return " \\\n  ".join(parts)


def sample_requests(ep: dict) -> str:
    header = auth_header(ep)
    key, _, value = (header or "").partition(": ")
    headers = {key: value} if header else {}
    for extra in ep.get("extra_headers", []):
        k, _, v = extra.partition(": ")
        headers[k] = v
    lines = ["import requests", "", f'BASE = "{BASE}"']
    if headers:
        lines.append(f"headers = {py_literal(headers)}")
    call_args = [f'f"{{BASE}}{ep.get("example_path", ep["path"])}"']
    if ep.get("body"):
        lines.append(f"payload = {py_literal(ep['body'])}")
        call_args.append("json=payload")
    if ep.get("query"):
        lines.append(f"params = {py_literal(ep['query'])}")
        call_args.append("params=params")
    if headers:
        call_args.append("headers=headers")
    lines += ["", f"response = requests.{ep['method'].lower()}({', '.join(call_args)})", "print(response.status_code, response.json())"]
    return "\n".join(lines)


def sample_js(ep: dict) -> str:
    headers = {}
    header = auth_header(ep)
    if header:
        k, _, v = header.partition(": ")
        headers[k] = v
    for extra in ep.get("extra_headers", []):
        k, _, v = extra.partition(": ")
        headers[k] = v
    if ep.get("body"):
        headers["Content-Type"] = "application/json"
    url = ep.get("example_path", ep["path"])
    if ep.get("query"):
        url += "?" + "&".join(f"{k}={v}" for k, v in ep["query"].items())
    opts = [f'  method: "{ep["method"]}",']
    if headers:
        opts.append("  headers: " + json.dumps(headers, indent=2).replace("\n", "\n  ") + ",")
    if ep.get("body"):
        opts.append("  body: JSON.stringify(" + json.dumps(ep["body"], indent=2, ensure_ascii=False).replace("\n", "\n  ") + "),")
    return f'const BASE = "{BASE}";\n\nconst response = await fetch(`${{BASE}}{url}`, {{\n' + "\n".join(opts) + "\n});\nconsole.log(response.status, await response.json());"


def examples(ep: dict) -> list[dict]:
    out = [{"lang": "curl", "label": "cURL", "code": sample_curl(ep)}]
    if ep.get("sdk"):
        out.append({"lang": "python-sdk", "label": "Python SDK", "code": "from paysawa import Client\n\nclient = Client.from_env()\n\n" + ep["sdk"] if not ep["sdk"].startswith("# The SDK") and "from paysawa import Client" not in ep["sdk"] else ep["sdk"]})
    out.append({"lang": "python", "label": "Python (requests)", "code": sample_requests(ep)})
    out.append({"lang": "javascript", "label": "JavaScript", "code": sample_js(ep)})
    return out


def response_blocks(ep: dict) -> list[dict]:
    return [{"status": r["status"], "title": r["title"], "code": json.dumps(r["body"], indent=2, ensure_ascii=False)} for r in ep["responses"]]


# ================================================================== languages
LANGS = ("en", "fr")
GROUP_FR = {"Introduction": "Introduction", "Apps API": "API Apps", "API v1": "API v1", "Webhooks": "Webhooks",
            "Payment links": "Liens de paiement", "SDKs": "SDK", "Reference": "Référence"}
MD = {
    "en": {"auth": "Authentication", "headers": "Headers", "params": "Parameters", "examples": "Examples", "responses": "Responses", "notes": "Notes",
           "cols": ("Name", "Type", "Required", "Description"), "yes": "yes", "no": "no", "none": "None.",
           "token": "`Authorization: Token <token>` (token from [{t}](#/token)).",
           "apikey": "`Authorization: Bearer sk_test_...` or `sk_live_...` (secret API key).",
           "index": "Paysawa documentation", "index_sub": "Version {v}. Base URL: `{b}`. A browsable version is in `docs_site/index.html`.", "other": "Français : [fr/README.md](fr/README.md)"},
    "fr": {"auth": "Authentification", "headers": "En-têtes", "params": "Paramètres", "examples": "Exemples", "responses": "Réponses", "notes": "Notes",
           "cols": ("Nom", "Type", "Obligatoire", "Description"), "yes": "oui", "no": "non", "none": "Aucune.",
           "token": "`Authorization: Token <jeton>` (jeton obtenu avec [{t}](#/token)).",
           "apikey": "`Authorization: Bearer sk_test_...` ou `sk_live_...` (clé API secrète).",
           "index": "Documentation Paysawa", "index_sub": "Version {v}. URL de base : `{b}`. Une version navigable se trouve dans `docs_site/index.html`.", "other": "English: [../README.md](../README.md)"},
}


def localize(ep: dict, lang: str) -> dict:
    """Title, texts, parameter descriptions and response titles of an endpoint in one language."""
    if lang == "en":
        return {"title": ep["title"], "summary": ep["summary"], "description": ep["description"], "notes": ep["notes"],
                "params": ep["params"], "headers": ep.get("headers", []), "resp_titles": [r["title"] for r in ep["responses"]]}
    tr = FR[ep["id"]]
    for prm in ep["params"]:
        assert prm["name"] in tr["params"], f"{ep['id']}: no French text for parameter {prm['name']}"
    for h in ep.get("headers", []):
        assert h["name"] in tr.get("headers", {}), f"{ep['id']}: no French text for header {h['name']}"
    assert len(tr["responses"]) == len(ep["responses"]), f"{ep['id']}: French response titles do not match"
    return {"title": tr["title"], "summary": tr["summary"], "description": tr["description"], "notes": tr["notes"],
            "params": [dict(p, description=tr["params"][p["name"]]) for p in ep["params"]],
            "headers": [dict(h, description=tr["headers"][h["name"]]) for h in ep.get("headers", [])], "resp_titles": tr["responses"]}


# ================================================================== pages
def load_pages(directory: Path) -> list[dict]:
    pages = []
    for path in sorted(directory.glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        meta_text, _, body = raw.partition("\n---\n") if raw.startswith("---\n") else ("", "", raw)
        meta = dict(re.findall(r"^(\w+):\s*(.+)$", meta_text, re.M))
        pages.append({"id": meta["id"], "title": meta["title"], "group": meta["group"], "order": int(meta.get("order", 99)), "md": body.strip() + "\n"})
    return pages


def file_for(item_id: str, kind_by_id: dict[str, str]) -> str:
    return f"api/{item_id}.md" if kind_by_id[item_id] == "endpoint" else f"{item_id}.md"


def rewrite_links(md: str, current_is_endpoint: bool, kind_by_id: dict[str, str]) -> str:
    def repl(m: re.Match) -> str:
        target = m.group(1)
        if target not in kind_by_id:
            return m.group(0)
        path = file_for(target, kind_by_id)
        if current_is_endpoint:
            path = "../" + path if not path.startswith("api/") else path[4:]
        return f"]({path})"
    return re.sub(r"\]\(#/([a-z0-9-]+)\)", repl, md)


def endpoint_markdown(ep: dict, lang: str) -> str:
    L, S = localize(ep, lang), MD[lang]
    lines = [f"# {L['title']}", "", f"`{ep['method']} {ep['path']}`", "", L["summary"], ""]
    if L["description"]:
        lines += [L["description"], ""]
    auth_text = {"none": S["none"], "token": S["token"].format(t=localize(ENDPOINTS[0], lang)["title"]), "apikey": S["apikey"]}[ep["auth"]]
    lines += [f"**{S['auth']}:** {auth_text}", ""]
    for title, items in ((S["headers"], L["headers"]), (S["params"], L["params"])):
        if items:
            c = S["cols"]
            lines += [f"## {title}", "", f"| {c[0]} | {c[1]} | {c[2]} | {c[3]} |", "|---|---|---|---|"]
            lines += [f"| `{x['name']}` | {x['type']} | {S['yes'] if x['required'] else S['no']} | {x['description']} |" for x in items]
            lines.append("")
    lines += [f"## {S['examples']}", ""]
    for ex in examples(ep):
        lines += [f"### {ex['label']}", "", f"```{'bash' if ex['lang'] == 'curl' else 'javascript' if ex['lang'] == 'javascript' else 'python'}", ex["code"], "```", ""]
    lines += [f"## {S['responses']}", ""]
    for r, title in zip(response_blocks(ep), L["resp_titles"]):
        lines += [f"### {r['status']} {title}", "", "```json", r["code"], "```", ""]
    if L["notes"]:
        lines += [f"## {S['notes']}", "", L["notes"], ""]
    return "\n".join(lines)


def main() -> None:
    pages = {lang: load_pages(HERE / ("pages" if lang == "en" else "pages_fr")) for lang in LANGS}
    assert {p["id"] for p in pages["en"]} == {p["id"] for p in pages["fr"]}, "English and French pages must have the same ids"
    kind_by_id = {p["id"]: "page" for p in pages["en"]} | {e["id"]: "endpoint" for e in ENDPOINTS}

    # ---------------- Markdown files (docs/ in English, docs/fr/ in French)
    for lang in LANGS:
        base_dir = ROOT / "docs" if lang == "en" else ROOT / "docs" / "fr"
        (base_dir / "api").mkdir(parents=True, exist_ok=True)
        for page in pages[lang]:
            md = rewrite_links(page["md"], False, kind_by_id).replace(BASE, config.BASE_URL)
            (base_dir / f"{page['id']}.md").write_text(md, encoding="utf-8")
        for ep in ENDPOINTS:
            md = rewrite_links(endpoint_markdown(ep, lang), True, kind_by_id).replace(BASE, config.BASE_URL)
            (base_dir / "api" / f"{ep['id']}.md").write_text(md, encoding="utf-8")
        S = MD[lang]
        index = [f"# {S['index']}", "", S["index_sub"].format(v=config.VERSION, b=config.BASE_URL), "", S["other"], ""]
        for group in GROUP_ORDER:
            items = [(p["order"], p["title"], file_for(p["id"], kind_by_id)) for p in pages[lang] if p["group"] == group]
            items += [(100 + n, localize(e, lang)["title"] + f" (`{e['method']} {e['path']}`)", file_for(e["id"], kind_by_id)) for n, e in enumerate(ENDPOINTS) if e["group"] == group]
            if items:
                index += [f"## {GROUP_FR[group] if lang == 'fr' else group}", ""] + [f"- [{title}]({path})" for _, title, path in sorted(items)] + [""]
        (base_dir / "README.md").write_text("\n".join(index), encoding="utf-8")

    # ---------------- website data: text per language, code samples shared
    site_langs = {}
    for lang in LANGS:
        groups = []
        for group in GROUP_ORDER:
            items = []
            for page in sorted((p for p in pages[lang] if p["group"] == group), key=lambda p: p["order"]):
                body = md_to_html(page["md"])
                items.append({"id": page["id"], "title": page["title"], "kind": "page", "html": body, "text": strip_tags(body)})
            for ep in (e for e in ENDPOINTS if e["group"] == group):
                L = localize(ep, lang)
                desc = md_to_html(L["description"]) if L["description"] else ""
                notes = md_to_html(L["notes"]) if L["notes"] else ""
                items.append({
                    "id": ep["id"], "title": L["title"], "kind": "endpoint", "method": ep["method"], "path": ep["path"], "auth": ep["auth"],
                    "summary": inline(L["summary"]), "descriptionHtml": desc, "notesHtml": notes,
                    "headers": [dict(x, descriptionHtml=inline(x["description"])) for x in L["headers"]],
                    "params": [dict(x, descriptionHtml=inline(x["description"])) for x in L["params"]],
                    "responseTitles": L["resp_titles"],
                    "text": strip_tags(L["title"] + " " + L["summary"] + " " + desc + " " + notes + " " + ep["path"] + " " + " ".join(x["name"] for x in L["params"])),
                })
            if items:
                groups.append({"title": GROUP_FR[group] if lang == "fr" else group, "items": items})
        site_langs[lang] = {"groups": groups}
    code = {ep["id"]: {"examples": examples(ep), "responses": response_blocks(ep)} for ep in ENDPOINTS}
    data = {"version": config.VERSION, "baseUrl": config.BASE_URL, "langs": site_langs, "code": code}
    (ROOT / "docs_site" / "assets").mkdir(parents=True, exist_ok=True)
    (ROOT / "docs_site" / "assets" / "content.js").write_text("window.DOCS = " + json.dumps(data, ensure_ascii=False) + ";\n", encoding="utf-8")
    print(f"built {len(pages['en'])} pages and {len(ENDPOINTS)} endpoints in {len(LANGS)} languages -> docs/, docs/fr/ and docs_site/assets/content.js")


if __name__ == "__main__":
    main()
