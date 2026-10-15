#!/usr/bin/env python3
"""Synchronise public bibliographic data, merge local additions, and prepare Jekyll.

Network access is confined to ``sync``. ``build`` is deterministic and offline.
The imported cache is atomically replaced only after a valid, non-empty import.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import html
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlparse
from urllib.request import Request, urlopen

import yaml

ROOT = Path(__file__).resolve().parents[1]
LABELS = {"article": "Article", "manuscript": "Author manuscript", "preprint": "Preprint",
          "hal": "HAL", "slides": "Slides", "code": "Code", "supplement": "Supplement",
          "poster": "Poster", "video": "Video", "read_only": "Read online", "thesis": "Thesis PDF"}
KIND_LABELS = {"article": "Article", "preprint": "Preprint", "thesis": "Doctoral thesis", "other": "Research output"}


def clean_text(value):
    return " ".join(html.unescape(re.sub(r"<[^>]*>", "", str(value or ""))).split())


def doi_value(value):
    text = unquote(str(value or "")).strip().lower()
    text = re.sub(r"^(?:doi:\s*|https?://(?:dx\.)?doi\.org/)", "", text)
    return text if re.fullmatch(r"10\.\d{4,9}/\S+", text) else ""


def arxiv_value(value):
    text = str(value or "").strip()
    text = re.sub(r"^https?://(?:www\.)?arxiv\.org/(?:abs|pdf)/", "", text, flags=re.I)
    text = re.sub(r"^arxiv:\s*", "", text, flags=re.I)
    return re.sub(r"(?:v\d+)?(?:\.pdf)?$", "", text).lower()


def allowed_url(value):
    text = str(value or "").strip()
    parsed = urlparse(text)
    if (text.startswith("/") and not text.startswith("//")) or (parsed.scheme in {"https", "http"} and parsed.netloc):
        return text
    raise ValueError(f"Expected an HTTP(S) URL or a site-relative file path, got {text!r}")


def canonical_alias(value):
    value = str(value).strip()
    if value.startswith("doi:") or doi_value(value):
        return "doi:" + doi_value(value)
    if value.lower().startswith("arxiv:"):
        return "arxiv:" + arxiv_value(value)
    return value.lower()


def aliases(record):
    result = {canonical_alias(x) for x in record.get("aliases", []) if x}
    if record.get("id"):
        result.add(str(record["id"]))
    if record.get("doi"):
        result.add("doi:" + doi_value(record["doi"]))
    if record.get("arxiv"):
        result.add("arxiv:" + arxiv_value(record["arxiv"]))
    for value in record.get("put_codes", []):
        result.add("orcid:" + str(value))
    return result - {"doi:", "arxiv:"}


def normalise_date(value):
    if isinstance(value, (dt.date, dt.datetime)):
        return value.strftime("%Y-%m-%d")
    parts = re.split(r"[-/]", str(value or ""))
    if not parts or not re.fullmatch(r"\d{4}", parts[0]):
        return ""
    numbers = [int(x) for x in parts if x]
    try:
        dt.date(numbers[0], numbers[1] if len(numbers) > 1 else 1, numbers[2] if len(numbers) > 2 else 1)
    except (ValueError, IndexError):
        raise ValueError(f"Invalid publication date: {value!r}") from None
    return "-".join([f"{numbers[0]:04d}"] + [f"{x:02d}" for x in numbers[1:]])


def author_record(value):
    if isinstance(value, str):
        value = {"name": value}
    result = dict(value)
    result["name"] = clean_text(result.get("name") or " ".join([result.get("given", ""), result.get("family", "")]))
    name = re.sub(r"[^a-z]", "", result["name"].lower())
    result["is_self"] = ("madrid" in name and ("ignacio" in name or name in {"imadrid", "madridi"})) or "0000-0001-7484-2073" in result.get("orcid", "")
    return result


def merge_record(old, new):
    """Merge known versions; keep the first record's identifier and legacy URL."""
    out = copy.deepcopy(old)
    combined_aliases = aliases(old) | aliases(new)
    rank = {"other": 0, "preprint": 1, "article": 2, "thesis": 2}
    new_wins = rank.get(new.get("kind"), 0) >= rank.get(old.get("kind"), 0)
    for key, value in new.items():
        if key in {"id", "url", "aliases", "links", "put_codes", "source"}:
            continue
        if value not in (None, "", [], {}) and (new_wins or key not in out or not out[key]):
            out[key] = copy.deepcopy(value)
    out["links"] = {**new.get("links", {}), **old.get("links", {})}
    out["aliases"] = sorted(combined_aliases)
    out["put_codes"] = sorted(set(old.get("put_codes", []) + new.get("put_codes", [])))
    out["source"] = sorted(set(old.get("source", []) + new.get("source", [])))
    return out


def apply_overrides(record, overrides):
    out = copy.deepcopy(record)
    for key, extra in overrides.items():
        if canonical_alias(key) not in aliases(out):
            continue
        if not isinstance(extra, dict):
            raise ValueError(f"Overrides for {key} must be a mapping")
        out["aliases"] = sorted(aliases(out) | {canonical_alias(x) for x in extra.get("aliases", [])})
        out["links"] = {**out.get("links", {}), **extra.get("links", {})}
        for field, value in extra.items():
            if field not in {"aliases", "links"}:
                out[field] = copy.deepcopy(value)
    return out


def read_yaml(path, default):
    return yaml.safe_load(path.read_text()) if path.exists() else default


def legacy_records(root):
    result = []
    for path in sorted((root / "_publications").glob("*.md")):
        pieces = path.read_text().split("---", 2)
        if len(pieces) < 3:
            raise ValueError(f"Missing front matter in {path}")
        fm = yaml.safe_load(pieces[1])
        pub_id = fm.get("publication_id", path.stem)
        links = {}
        doi = ""
        arxiv = ""
        for key in ("link", "paperurl", "paperreadonly", "code"):
            value = fm.get(key)
            if not value:
                continue
            if key == "paperreadonly":
                links["read_only"] = value
            elif key == "code":
                links["code"] = value
            elif "arxiv.org" in value:
                arxiv = arxiv_value(value)
                links["preprint"] = "https://arxiv.org/abs/" + arxiv
            elif "hal.science" in value or "archives-ouvertes.fr" in value:
                links["hal"] = value
            elif value.startswith("/"):
                links["manuscript"] = value
            else:
                links["article"] = value
                doi = doi_value(value) or doi
        for key in LABELS:
            if fm.get(key):
                links[key] = fm[key]
        result.append({"id": pub_id, "title": fm["title"], "date": normalise_date(fm.get("date")),
                       "venue": clean_text(fm.get("venue")), "kind": fm.get("kind") or ("preprint" if arxiv else "article"),
                       "doi": fm.get("doi") or doi, "arxiv": fm.get("arxiv") or arxiv, "authors": fm.get("authors") or [], "links": links,
                       "abstract": fm.get("abstract", ""), "note": fm.get("note", ""),
                       "url": fm.get("permalink", f"/publications/{path.stem}/"),
                       "legacy": True, "source": ["legacy"]})
    return result


def get_json(url, token="", user_agent="AcademicWebsite/1.0"):
    headers = {"Accept": "application/json", "User-Agent": user_agent}
    if token:
        headers["Authorization"] = "Bearer " + token
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers=headers), timeout=25) as response:
                return json.load(response)
        except HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504} or attempt == 2:
                raise
            time.sleep(2 ** (attempt + 1))


def orcid_record(work):
    title = clean_text((work.get("title") or {}).get("title", {}).get("value"))
    if not title:
        raise ValueError("ORCID returned a work without a title")
    identifiers = (work.get("external-ids") or {}).get("external-id", [])
    doi = arxiv = ""
    links = {}
    extra_aliases = []
    for identifier in identifiers:
        if identifier.get("external-id-relationship") not in {"self", "version-of", None}:
            continue
        typ = identifier.get("external-id-type", "").lower()
        val = identifier.get("external-id-value", "")
        if typ == "doi" and doi_value(val):
            doi = doi_value(val)
        elif typ == "arxiv":
            arxiv = arxiv_value(val)
            links["preprint"] = "https://arxiv.org/abs/" + arxiv
        elif typ == "hal":
            val = str(val).strip().lower()
            extra_aliases.append("hal:" + val)
            links["hal"] = "https://hal.science/" + val
    typ = work.get("type", "")
    kind = "thesis" if typ == "dissertation-thesis" else "preprint" if typ in {"working-paper", "preprint"} else "article" if typ in {"journal-article", "conference-paper"} else "other"
    if doi:
        links["article"] = "https://doi.org/" + doi
    date = work.get("publication-date") or {}
    date = normalise_date("-".join(str((date.get(k) or {}).get("value")) for k in ("year", "month", "day") if (date.get(k) or {}).get("value")))
    authors = []
    for contributor in (work.get("contributors") or {}).get("contributor", []):
        role = (contributor.get("contributor-attributes") or {}).get("contributor-role")
        if role not in {None, "author"}:
            continue
        credit = (contributor.get("credit-name") or {}).get("value")
        if credit:
            authors.append(author_record({"name": credit, "orcid": (contributor.get("contributor-orcid") or {}).get("uri", "")}))
    put_code = int(work["put-code"])
    identity = ("doi:" + doi) if doi else ("arxiv:" + arxiv) if arxiv else "orcid:" + str(put_code)
    return {"id": "work-" + hashlib.sha256(identity.encode()).hexdigest()[:12], "title": title,
            "doi": doi, "arxiv": arxiv, "kind": kind, "date": date,
            "venue": clean_text((work.get("journal-title") or {}).get("value")), "authors": authors,
            "links": links, "put_codes": [put_code], "aliases": extra_aliases, "source": ["orcid"]}


def enrich_crossref(record, user_agent):
    if not record.get("doi"):
        return record
    try:
        response = get_json("https://api.crossref.org/works/" + quote(record["doi"], safe=""), user_agent=user_agent)
        message = response["message"]
        out = copy.deepcopy(record)
        names = [author_record({"given": x.get("given", ""), "family": x.get("family", ""), "name": x.get("name", ""), "orcid": x.get("ORCID", "")}) for x in message.get("author", [])]
        if names:
            out["authors"] = names
        if message.get("container-title"):
            out["venue"] = clean_text(message["container-title"][0])
        if not out.get("date"):
            date_parts = (message.get("published") or message.get("issued") or {}).get("date-parts", [[]])[0]
            out["date"] = normalise_date("-".join(map(str, date_parts)))
        for field in ("volume", "issue", "page"):
            if message.get(field):
                out["pages" if field == "page" else field] = clean_text(message[field])
        if message.get("abstract"):
            out["abstract"] = clean_text(message["abstract"])
        out["source"] = sorted(set(out.get("source", []) + ["crossref"]))
        return out
    except (HTTPError, URLError, TimeoutError, KeyError, ValueError) as exc:
        print(f"Warning: DOI enrichment unavailable for {record['doi']}: {type(exc).__name__}", file=sys.stderr)
        return record


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def sync(root, strict=False):
    config = read_yaml(root / "_config.yml", {})["publication_sync"]
    cache = root / "_data/publications_imported.json"
    previous = json.loads(cache.read_text()) if cache.exists() else {"records": []}
    user_agent = config.get("user_agent", "AcademicWebsite/1.0")
    token = os.environ.get("ORCID_READ_TOKEN", "")
    try:
        summary = get_json(f"https://pub.orcid.org/v3.0/{config['orcid']}/works", token=token, user_agent=user_agent)
        groups = summary.get("group")
        if not isinstance(groups, list) or not groups:
            raise ValueError("No public works returned; keeping the previous bibliography")
        imported = []
        for group in groups:
            summaries = group.get("work-summary", [])
            if not summaries:
                raise ValueError("Malformed ORCID work group")
            # Import all versions in the group so their identifiers and resource links survive.
            for work in summaries:
                time.sleep(1.1)
                try:
                    full = get_json(f"https://pub.orcid.org/v3.0/{config['orcid']}/work/{work['put-code']}", token=token, user_agent=user_agent)
                except (HTTPError, URLError, TimeoutError):
                    full = work
                record = orcid_record(full)
                for old in previous["records"]:
                    if aliases(old) & aliases(record):
                        record = merge_record(old, record)
                        break
                if config.get("crossref", True):
                    record = enrich_crossref(record, user_agent)
                imported.append(record)
        overrides = read_yaml(root / "_data/publication_overrides.yml", {}) or {}
        # The original site contains works that are not yet on ORCID. Refresh their DOI metadata too.
        for legacy in legacy_records(root):
            legacy = apply_overrides(legacy, overrides)
            if legacy.get("doi") and not any(aliases(legacy) & aliases(x) for x in imported):
                for old in previous["records"]:
                    if aliases(old) & aliases(legacy):
                        legacy = merge_record(old, legacy)
                        break
                enriched = enrich_crossref(legacy, user_agent)
                # Do not cache manual selection flags, project tags, URLs, or file attachments.
                enriched = {k: v for k, v in enriched.items() if k not in {"selected", "projects", "url", "legacy", "hidden", "note"}}
                enriched["links"] = {k: v for k, v in enriched.get("links", {}).items() if v and not str(v).startswith("/")}
                imported.append(enriched)
        if not imported:
            raise ValueError("Empty import")
        payload = {"orcid": config["orcid"], "fetched_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(), "records": imported}
        atomic_json(cache, payload)
        print(f"Imported {len(imported)} source records from ORCID and curated DOIs.")
        return True
    except (HTTPError, URLError, TimeoutError, ValueError, KeyError) as exc:
        print(f"Warning: bibliography refresh failed ({type(exc).__name__}: {exc}). Cached records are unchanged.", file=sys.stderr)
        if strict or not previous["records"]:
            raise
        return False


def bibtex(record):
    def tex(value):
        escapes = {"\\": r"\textbackslash{}", "{": r"\{", "}": r"\}", "&": r"\&", "%": r"\%", "#": r"\#", "_": r"\_", "$": r"\$"}
        return "".join(escapes.get(character, character) for character in str(value or ""))
    kind = "phdthesis" if record["kind"] == "thesis" else "article" if record["kind"] == "article" else "misc"
    author_names = [(x["family"] + ", " + x["given"]) if x.get("family") and x.get("given") else x["name"] for x in record["authors"]]
    fields = {"title": record["title"], "author": " and ".join(author_names), "year": record.get("year"), "journal": record.get("venue") if kind == "article" else None, "doi": record.get("doi"), "eprint": record.get("arxiv"), "archivePrefix": "arXiv" if record.get("arxiv") else None, "volume": record.get("volume"), "pages": record.get("pages")}
    if kind == "phdthesis":
        fields["school"] = "École polytechnique"
    return "@" + kind + "{" + record["id"] + ",\n" + ",\n".join("  " + key + " = {" + tex(value) + "}" for key, value in fields.items() if value) + "\n}"


def primary_url(record):
    """Open the work at its source; retain local detail URLs for legacy references."""
    links = record.get("links", {})
    priorities = ["article", "preprint", "hal", "manuscript", "thesis"]
    if record.get("kind") == "preprint":
        priorities = ["preprint", "hal", "article", "manuscript"]
    elif record.get("kind") == "thesis":
        priorities = ["thesis", "hal", "article", "manuscript"]
    return next((links[key] for key in priorities if links.get(key)), record["url"])


def build(root):
    overrides = read_yaml(root / "_data/publication_overrides.yml", {}) or {}
    cache_path = root / "_data/publications_imported.json"
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {"records": []}
    manual = read_yaml(root / "_data/publications_manual.yml", []) or []
    records = []
    for raw in legacy_records(root) + manual + cache["records"]:
        record = apply_overrides(raw, overrides)
        # A new record can bridge several identifiers (for example, a preprint and journal DOI).
        matches = [i for i, current in enumerate(records) if aliases(current) & aliases(record)]
        if matches:
            target = matches[0]
            record = merge_record(records[target], record)
            for i in reversed(matches[1:]):
                record = merge_record(record, records.pop(i))
            records[target] = record
        else:
            records.append(record)
    ids = set()
    for index, record in enumerate(records):
        record = apply_overrides(record, overrides)
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", str(record.get("id", ""))):
            raise ValueError(f"Invalid stable publication identifier: {record.get('id')!r}")
        if record["id"] in ids:
            raise ValueError(f"Duplicate stable publication identifier: {record['id']}")
        ids.add(record["id"])
        record["title"] = clean_text(record["title"])
        record["authors"] = [author_record(x) for x in record.get("authors", [])]
        record["date"] = normalise_date(record.get("date"))
        record["year"] = int(record["date"][:4]) if record["date"] else None
        record["kind"] = record.get("kind", "other")
        record["kind_label"] = KIND_LABELS.get(record["kind"], "Research output")
        record["url"] = record.get("url") or f"/publications/{record['id']}/"
        if not record["url"].startswith("/publications/") or ".." in record["url"]:
            raise ValueError("Publication pages must stay under /publications/")
        record["links"] = {k: allowed_url(v) for k, v in record.get("links", {}).items() if v}
        record["primary_url"] = primary_url(record)
        record["resources"] = [{"label": LABELS.get(k, k.replace("_", " ").capitalize()), "url": v} for k, v in sorted(record["links"].items(), key=lambda item: list(LABELS).index(item[0]) if item[0] in LABELS else len(LABELS))]
        for custom in record.get("extra_resources", []):
            record["resources"].append({"label": clean_text(custom["label"]), "url": allowed_url(custom["url"])})
        record["bibtex"] = bibtex(record)
        records[index] = record
    records.sort(key=lambda record: (record.get("date", ""), record["title"]), reverse=True)
    atomic_json(root / "_data/publications.json", records)
    generated = root / "_generated/publications"
    generated.mkdir(parents=True, exist_ok=True)
    for path in generated.glob("*.md"):
        path.unlink()
    for record in records:
        if record.get("legacy"):
            continue
        front = {"layout": "publication", "title": record["title"], "publication_id": record["id"], "permalink": record["url"]}
        (generated / (record["id"] + ".md")).write_text("---\n" + yaml.safe_dump(front, sort_keys=False, allow_unicode=True) + "---\n")
    print(f"Built {len(records)} unique bibliography entries and {len(list(generated.glob('*.md')))} automatic detail pages.")
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["sync", "build"])
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--strict", action="store_true", help="Fail a refresh instead of falling back to the saved cache")
    args = parser.parse_args()
    if args.command == "sync":
        sync(args.root, strict=args.strict)
    build(args.root)


if __name__ == "__main__":
    main()
