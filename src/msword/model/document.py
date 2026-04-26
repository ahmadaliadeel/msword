"""Document stub — minimal owner of stories for find/replace.

Real implementation lands in `model-document-core` (unit 2). This stub only
holds the story list so the find engine can walk it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from msword.model.story import Story


@dataclass
class Document:
    stories: list[Story] = field(default_factory=list)

    def find_story(self, story_id: str) -> Story | None:
        for story in self.stories:
            if story.id == story_id:
                return story
        return None
