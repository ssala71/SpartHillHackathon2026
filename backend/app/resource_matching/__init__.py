"""Person B — Resources, inventory, and matching.

This package owns resource facts and matching ONLY. It never calls Bedrock and
never interprets raw user text. It consumes an already-extracted request
(`ExtractionResult`, produced by Person A) and returns a sourced match or an
explicit no-match. Keeping these concerns apart satisfies the spec requirement:
"keep resource facts separate from AI-generated interpretation."
"""
