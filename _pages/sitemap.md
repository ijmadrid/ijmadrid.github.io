---
layout: page
title: Sitemap
permalink: /sitemap/
---

- [About](/)
- [Research](/research/)
- [Publications](/publications/)
- [Teaching](/teaching/)
- [Curriculum vitæ](/cv/)
- [Scripts and software](/codes/)
- [Talks and presentations](/talks/)

## Research projects
{% for project in site.data.research %}
- [{{ project.title }}]({{ project.url | relative_url }})
{% endfor %}

## Publications
{% for publication in site.data.publications %}{% unless publication.hidden %}
- [{{ publication.title }}]({{ publication.primary_url }})
{% endunless %}{% endfor %}
