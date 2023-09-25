import dataclasses
from pathlib import Path
from typing import Any, Dict
import solara

import yaml


HERE = Path(__file__)


@dataclasses.dataclass
class Article:
    markdown: str
    title: str
    description: str


articles: Dict[str, Article] = {}

for file in (HERE.parent / "content/articles").glob("*.md"):
    content = file.read_text()
    lines = [k.strip() for k in content.split("\n")]
    frontmatter_start = lines.index("---", 0)
    frontmatter_end = lines.index("---", frontmatter_start + 1)
    yamltext = "\n".join(lines[frontmatter_start + 1 : frontmatter_end - 2])
    metadata = yaml.safe_load(yamltext)
    markdown = "\n".join(lines[frontmatter_end + 1 :])
    articles[file.stem] = Article(markdown=markdown, title=metadata["title"], description=metadata["description"])

