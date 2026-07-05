"""Versioned prompt templates (F35): Jinja2 files under prompts/, each with a
'#version:' header line. The renderer strips the header and logs a content
hash per render so every generation is traceable to an exact prompt."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

import structlog
from jinja2 import Environment, FileSystemLoader, StrictUndefined

log = structlog.get_logger(__name__)
_VERSION_RE = re.compile(r"^#version:\s*(\S+)\s*\n")


class PromptLibrary:
    def __init__(self, prompts_dir: Path) -> None:
        self.prompts_dir = prompts_dir
        self._env = Environment(
            loader=FileSystemLoader(str(prompts_dir)),
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=False,
        )

    def render(self, template_name: str, **variables) -> str:
        source, _, _ = self._env.loader.get_source(self._env, template_name)
        match = _VERSION_RE.match(source)
        version = match.group(1) if match else "unversioned"
        body = _VERSION_RE.sub("", source, count=1)
        rendered = self._env.from_string(body).render(**variables)
        prompt_hash = hashlib.sha256(rendered.encode("utf-8")).hexdigest()[:12]
        log.debug("prompt rendered", template=template_name, version=version,
                  hash=prompt_hash, chars=len(rendered))
        return rendered
