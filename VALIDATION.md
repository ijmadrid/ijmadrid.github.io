# Validation of the prepared update

Prepared from the user-supplied repository ZIP on 15 October 2026.

## Completed checks

- Fetched the public ORCID works and individual records successfully, using anonymous read access.
- Enriched available DOI records using Crossref. Checked the Myxobacteria paper against HAL and Crossref.
- Verified the newer CRN preprint against arXiv (2609.30970) and added it as a local record, linked to the reaction-networks project.
- Produced ten distinct bibliography entries: seven articles, two preprints and the doctoral thesis. The preprint and journal versions of the ergodicity paper appear once, with all resource links.
- Built successfully with Ruby 3.3.9 and Jekyll 4.4.1, including a production build with strict front-matter checking.
- Checked all 30 generated HTML pages for missing local links, images, anchors, duplicate HTML identifiers and unresolved Liquid output. Passed.
- Confirmed the homepage has four project cards in a horizontal row, including electron counting in biosensors, and three selected publications; the research index has four projects; the teaching page has three course entries. Project cards have no small topic labels above their names.
- Confirmed that navigation sits above the main content; the sidebar has no profession subtitle; academic supervision appears in About; QBIO is a prominent affiliation link.
- Confirmed all ten publication titles open an external source or the thesis PDF directly. Nine articles and preprints share a single list, with two visible Preprint markers; the Ph.D. thesis has its own section below.
- Checked that education markers contain dates only and both engineering degree titles are explicit.
- Passed twelve regression checks covering version merging, stable URLs, attachment retention, cache preservation on API failures, DOI normalisation, valid resource URLs, compound surnames in BibTeX and publication title destinations.
- Preserved the supplied PDFs and portrait without altering their bytes.
- Retained the existing Google Analytics configuration for production. The standalone preview omits analytics and embeds its images and stylesheet for local use.
- Checked the standalone preview's 25 local page routes, embedded images, unique identifiers, navigation targets and JavaScript syntax.
- Included the project-row controls in both the live Jekyll build and standalone HTML. Checked control boundaries, card-sized scrolling and reduced-motion behaviour with a DOM simulation; touch interaction and visual layout remain part of browser review.
- Verified the binary patch against a clean extraction of the original ZIP; it applies without conflicts and reproduces every tracked updated file exactly.

## Verification limits

A browser automation capability was unavailable in this environment. The responsive CSS and standalone preview have been structurally checked, but browser screenshots and interactive visual inspection were not performed. Review the supplied preview in your own browser before merging.

GitHub Actions publication has not been run against the user's repository. The package is prepared for review and upload; it has not changed the live website. Set the Pages publishing source to GitHub Actions as described in UPDATE_GUIDE.md.
