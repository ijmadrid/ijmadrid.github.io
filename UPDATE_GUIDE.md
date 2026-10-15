# Website update guide

This update retains Jekyll and the existing `https://ijmadrid.github.io` address. The site stays on GitHub Pages. The original PDFs and portrait are preserved at their existing paths.

## Publish the update

The delivery package contains a complete source snapshot under `repository/`, a patch against the uploaded ZIP under `update.patch`, a standalone preview, and a changed-file inventory. The ZIP is a working copy, not a new Git repository.

The recommended route is to apply the patch in your existing local clone, on a review branch:

```bash
cd /path/to/your/ijmadrid.github.io
git switch -c website-refresh
git apply --check /path/to/unpacked-package/update.patch
git apply /path/to/unpacked-package/update.patch
git add -A
git commit -m "Refresh website layout and publication management"
git push -u origin website-refresh
```

Open a pull request on GitHub and merge it when ready. The patch is based on the supplied repository ZIP; `git apply --check` stops before changing files if your working copy differs in a conflicting way. If that happens, use the complete source snapshot to review and apply the conflicting changes manually.

If copying the complete snapshot instead, copy the contents of `repository/` into your existing clone, preserve its `.git` directory, and remove **only** the obsolete paths listed in `DELETED_FILES.txt`. In particular, remove the old `jekyll.yml` workflow and `_pages/publications.md`; otherwise, you will retain competing deployment workflows or duplicate publication-index pages. Do not create a new repository or rename the existing one.

Once the changes are merged:

1. In the website repository, open **Settings → Pages**.
2. Set **Build and deployment → Source** to **GitHub Actions**.
3. In **Actions**, open **Build and publish website**. If the merge did not already start a run, choose **Run workflow** on the default branch (`master` for the supplied archive).
4. Wait for the build and deploy jobs to complete. The site remains at `https://ijmadrid.github.io`.

The supplied workflow handles pushes to the default branch, pull-request build checks, a weekly publication refresh, and a manual refresh. A preview/review branch does not deploy or push changes into the default branch.

No ORCID login or token was needed for the initial public-data import. If anonymous access is ever limited, an optional **Actions secret** named `ORCID_READ_TOKEN` can hold an ORCID `/read-public` token. Keep tokens in GitHub Secrets; the source and website do not contain them.

## Edit the website

| Content | File |
| --- | --- |
| Short homepage introduction | `_pages/about.md` |
| Sidebar name, portrait and email | `profile` in `_config.yml` |
| Scholar, ORCID and social links | `author` in `_config.yml` |
| Navigation | `_data/navigation.yml` |
| Project cards, thumbnails and order | `_data/research.yml` |
| Full project descriptions | `_projects/*.md` |
| CV page | `_pages/cv.md` |
| CV PDF | `files/CV.pdf` |
| Teaching entries | `_teaching/*.md` |
| Layout and typography | `assets/css/site.css` |
| Publication attachments and editorial choices | `_data/publication_overrides.yml` |
| Additional works not available in imported data | `_data/publications_manual.yml` |

The four `featured: true` projects form the homepage's horizontally scrollable row, including electron counting in biosensors. Visitors can swipe, scroll sideways or use the arrow buttons. Change the `featured` flags or their order to change this selection. The research index shows the projects in a regular grid. The portrait and reinforcement figure are reused from the current site. The reaction-network and electron-transfer thumbnails are schematic SVGs, clearly labelled as such on their project pages; replace them with your own figures whenever you prefer.

The design deliberately stays light, including when a visitor has dark mode enabled. The main navigation sits above the content; the sidebar contains the portrait, name, affiliation and contact links. Academic background and supervision appear within About. On narrow screens, the portrait and profile move above the main content and navigation wraps. The homepage project row shows one full card and a glimpse of the next; the research index stacks its cards. All projects are exposed when printing. The small arrow-button script is in `assets/js/projects.js`; native horizontal scrolling remains available without JavaScript.

## How publications work

There are three source layers:

1. `_data/publications_imported.json`: a saved public ORCID import, enriched with DOI metadata from Crossref. The importer also refreshes curated DOIs found in the existing publication entries. This file is managed automatically.
2. Existing `_publications/*.md` files and optional `_data/publications_manual.yml` records: local works and legacy page addresses. The initial seven publication entries remain available at their old addresses.
3. `_data/publication_overrides.yml`: your attachments, selection flags, project tags, corrections and explicit version associations. Automatic refreshes never edit this file.

The build merges these sources into `_data/publications.json`. Articles and preprints appear together in reverse chronological order, with a visible **Preprint** marker. The Ph.D. thesis appears in its own section below that list. Titles open the journal, arXiv, HAL or an available manuscript directly; attachment links remain alongside each entry. The build retains legacy detail-page addresses and generates detail pages for imported works for compatibility and indexing. You do not need a new Markdown file for each imported publication.

Entries are matched using stable identifiers, not guessed from their titles. The existing ergodicity journal article, arXiv preprint and HAL record are explicitly associated so that they appear once with all their links. A published version takes priority over preprint metadata when the association is known.

### Attach a manuscript, slides or code

Upload the file into `files/` and add a link to the matching override. For example:

```yaml
ergodicity:
  selected: true
  projects: [cell-growth]
  links:
    manuscript: /files/AM_Exponential_ergodicity_of_a_degenerate_age_size_piecewise_deterministic_process.pdf
    slides: /files/ergodicity-slides.pdf
    code: https://github.com/YOUR-ACCOUNT/YOUR-REPOSITORY
```

The slides/code paths above are examples; add only files and repositories that actually exist. The manuscript link is already present in this update.

Supported link keys include `article`, `manuscript`, `preprint`, `hal`, `slides`, `code`, `supplement`, `poster`, `video`, `read_only`, and `thesis`. Set a link to `null` to remove it. Add arbitrary labelled links with:

```yaml
ergodicity:
  extra_resources:
    - label: Seminar recording
      url: https://example.org/recording
```

For a newly imported work, find its `id` or DOI in `_data/publications.json`. You can use either as the override key:

```yaml
'doi:10.1000/replace-with-the-real-doi':
  selected: true
  projects: [reinforcement]
  links:
    slides: /files/my-talk.pdf
```

`selected: true` displays the work on the homepage. `hidden: true` removes it from public lists; an already existing legacy detail page is retained, so this flag is an editorial filter rather than an access restriction. Projects may be `reinforcement`, `cell-growth`, `reaction-networks`, or `biosensors`.

### Associate a preprint with a journal article

Add the other identifiers to the override for the existing entry:

```yaml
my-stable-paper-id:
  aliases:
    - doi:10.1000/replace-with-the-real-doi
    - arxiv:2601.12345
```

These identifiers are illustrative. Use the real DOI/arXiv identifier. This preserves the existing page address and attachments when a published version is imported. When adding a new DOI to an entry that already exists, include it under `aliases` to retain the association to the previous identifier. A deliberate local `title`, `date`, `venue`, `authors`, or `kind` override takes priority over imported metadata until you remove it.

### Add a work manually

Add a record to `_data/publications_manual.yml`:

```yaml
- id: my-new-paper
  title: Full title of the work
  date: '2026-10'
  kind: preprint
  authors:
    - name: Ignacio Madrid
      given: Ignacio
      family: Madrid
  links:
    preprint: https://example.org/your-preprint
  projects: [reinforcement]
```

Use a lowercase stable `id`, a real title, the actual authors, and valid URLs. Valid kinds are `article`, `preprint`, `thesis`, and `other`. The importer does not need network access to build local additions. New `_publications/*.md` files are also supported when you want a custom page body; `publication_id` in their front matter can supply the stable identifier.

### Refresh metadata

The workflow refreshes on Mondays at 05:23 UTC (14:23 Japan time). You can also use **Actions → Build and publish website → Run workflow**, on the default branch, with **Refresh public ORCID and DOI metadata** enabled. New public ORCID works are imported automatically. Works missing from ORCID can remain local or be added to ORCID later.

If ORCID is unavailable or unexpectedly returns an empty public record, the previous saved bibliography is retained. If DOI enrichment is unavailable, known author lists are retained. The public pages are generated during the build, so visitors do not depend on an API request to see publications.

GitHub may disable scheduled workflows after prolonged repository inactivity. Re-enable the workflow in Actions if necessary. If branch protection prevents the workflow's bibliography-cache commit, either permit this repository's automation to update the cache, or remove the **Record refreshed bibliography** step; the workflow can still refresh and deploy, but that fallback does not persist refreshed metadata into the repository. A publication API outage does not erase locally supplied records or resource links.

## Build locally (optional)

GitHub builds the website for you; a local Ruby installation is needed only if you want to run Jekyll on your computer. With Ruby 3.3, Bundler and Python 3.10+ installed:

```bash
python3 -m pip install -r requirements.txt
bundle install
python3 scripts/publications.py build
bundle exec jekyll serve
```

Then open `http://localhost:4000`. To fetch new public metadata locally, replace the `build` command with:

```bash
python3 scripts/publications.py sync
```

For a check without serving:

```bash
python3 scripts/publications.py build
python3 -m unittest discover -s tests -v
bundle exec jekyll build --strict_front_matter
python3 scripts/check_site.py _site
```

Do not edit `_data/publications.json` or `_generated/` directly; they are regenerated. Keep the saved imported cache and `Gemfile.lock` in Git. `_generated/` and `_site/` are build outputs and are ignored by Git.

## Initial migration notes

- Seven legacy publication entries were reconciled with live public ORCID and DOI data. With the newer CRN preprint, the bibliography contains ten distinct works: seven articles, two preprints and the doctoral thesis.
- *Large-deviations theory for growing chemical reaction networks* (Gagrani, Madrid and Kobayashi, arXiv:2609.30970, submitted 25 September 2026) was verified against arXiv and added to `publications_manual.yml`, as it was absent from the public ORCID import. Its arXiv identifier and DOI alias will associate it with a future ORCID import.
- The 2021 nanowire-biosensor paper was found in ORCID and added automatically.
- The ergodicity preprint and published article are one bibliography entry with DOI, arXiv, HAL, manuscript and read-online links.
- The Myxobacteria paper's DOI, date and author list were checked against HAL and Crossref. The original site listed a collaborator who is not in the published author list; the bibliography uses the published metadata.
- Three teaching files were given `.md` extensions so that they render consistently as Jekyll collection documents.
- The two original deployment workflows were consolidated into one. Template demonstration pages remain in the source but are excluded from publication.
- Existing PDFs, including the CV, thesis and author manuscript, are unchanged. Existing Google Analytics configuration is retained for production builds.
- The web CV now uses dates in the education column and full engineering degree titles. Education dates were checked against the supplied CV PDF and the existing Ph.D. defence date.
