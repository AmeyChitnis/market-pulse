"""
Serves the category catalog to the frontend.

Labels and sections live in config.yaml, not in the database - so the picker UI
is built from this endpoint rather than from distinct values in `items`. That
means renaming "Ritual" to "Omens" is a YAML edit, and it stays correct even
for categories that have no rows yet.
"""

from fastapi import APIRouter

from app.config import settings

router = APIRouter(tags=["categories"])


@router.get("/categories")
def list_categories():
    return [
        {
            "game": source.game,
            "league": source.league,
            "sections": [
                {
                    "name": section,
                    "categories": [
                        {
                            "type": c.type,
                            "label": c.display_label,
                            "endpoint": c.endpoint.value,
                        }
                        for c in source.categories
                        if c.section == section
                    ],
                }
                # dict.fromkeys preserves the order they appear in config.yaml,
                # so the UI grouping matches the file you edit.
                for section in dict.fromkeys(c.section for c in source.categories)
            ],
        }
        for source in settings.sources
    ]
