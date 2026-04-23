"""Analysis package.

Keep this module side-effect free so importing submodules like
`ai_news_digest.analysis.trends` does not pull in weekly synthesis code and
create circular imports during fresh-process imports.
"""
