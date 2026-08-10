"""Unilog house-style compliance.

The organizers' content guidelines are a *specification*, not a style
suggestion: a value written in the wrong unit abbreviation, the wrong casing or
outside a controlled vocabulary is wrong even when it is factually true. Their
own guide is blunt about it — "a fluent description made of invented values
scores zero".

Everything in this package is therefore rule-driven and data-backed. The rules
that Unilog owns (approved units, approved brands, permitted attribute values,
field formulas) live in `app/data/unilog/` as JSON, so when their spreadsheets
arrive the change is a data drop, not a rewrite. The stub tables shipped here
are marked with a `source` of `provisional` and every loader reports it, so no
output can quietly claim compliance with a standard we have not actually read.
"""
