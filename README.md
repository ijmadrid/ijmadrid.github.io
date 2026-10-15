# Ignacio Madrid — personal website

Jekyll source for https://ijmadrid.github.io.

The site uses a light editorial layout with a portrait sidebar, project figures, and an automatically maintained bibliography.

Read [UPDATE_GUIDE.md](UPDATE_GUIDE.md) for publication setup, deployment, adding manuscripts/slides, and everyday editing.

## Local preview

With Ruby 3.3, Bundler and Python 3.10+:

```bash
python3 -m pip install -r requirements.txt
bundle install
python3 scripts/publications.py build
bundle exec jekyll serve
```

## Validation

```bash
python3 -m unittest discover -s tests -v
python3 scripts/publications.py build
bundle exec jekyll build --strict_front_matter
python3 scripts/check_site.py _site
```

GitHub Actions builds and publishes the site, and refreshes public ORCID/DOI metadata weekly. It preserves manual attachments and the last successful import when a source is unavailable.

The original source was based on AcademicPages / Minimal Mistakes, © Michael Rose and contributors, under the MIT licence. The existing licence and legacy template source are retained. The current editorial layouts and publication tools are custom additions.
