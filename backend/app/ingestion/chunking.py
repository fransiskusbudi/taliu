"""Chunks the structured resume markdown into sections with metadata."""

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ResumeChunk:
    text: str
    metadata: dict = field(default_factory=dict)


def parse_resume(filepath: str) -> list[ResumeChunk]:
    """Parse resume.md into semantically meaningful chunks with metadata."""
    content = Path(filepath).read_text(encoding="utf-8")
    chunks: list[ResumeChunk] = []

    # Split into major sections by '---' separator
    sections = re.split(r"\n---\n", content)

    for section in sections:
        section = section.strip()
        if not section:
            continue

        # Header / Contact Info section
        if section.startswith("# Fransiskus"):
            chunks.append(_parse_contact_section(section))

        # Work Experience section
        elif "## Work Experience" in section:
            chunks.extend(_parse_work_experience(section))

        # Education section
        elif "## Education" in section:
            chunks.append(_parse_education(section))

        # Technologies section
        elif "## Technologies" in section:
            chunks.append(_parse_technologies(section))

    return chunks


def _parse_contact_section(section: str) -> ResumeChunk:
    return ResumeChunk(
        text=section,
        metadata={
            "section": "contact",
            "profile_id": "frans",
        },
    )


def _parse_work_experience(section: str) -> list[ResumeChunk]:
    """Split work experience into one chunk per role."""
    chunks = []
    # Split by ### headers (each role)
    roles = re.split(r"(?=^### )", section, flags=re.MULTILINE)

    for role_block in roles:
        role_block = role_block.strip()
        if not role_block or role_block.startswith("## Work Experience"):
            continue

        # Parse role header: ### Title | Company | Date Range
        header_match = re.match(
            r"### (.+?) \| (.+?) \| (.+)", role_block
        )
        if header_match:
            title = header_match.group(1).strip()
            company = header_match.group(2).strip()
            date_range = header_match.group(3).strip()
        else:
            title, company, date_range = "Unknown", "Unknown", "Unknown"

        # Extract location
        location_match = re.search(r"\*\*Location:\*\* (.+)", role_block)
        location = location_match.group(1).strip() if location_match else "Unknown"

        chunks.append(
            ResumeChunk(
                text=role_block,
                metadata={
                    "section": "work_experience",
                    "role": title,
                    "company": company,
                    "date_range": date_range,
                    "location": location,
                    "profile_id": "frans",
                },
            )
        )

    return chunks


def _parse_education(section: str) -> ResumeChunk:
    return ResumeChunk(
        text=section,
        metadata={
            "section": "education",
            "profile_id": "frans",
        },
    )


def _parse_technologies(section: str) -> ResumeChunk:
    return ResumeChunk(
        text=section,
        metadata={
            "section": "technologies",
            "profile_id": "frans",
        },
    )
