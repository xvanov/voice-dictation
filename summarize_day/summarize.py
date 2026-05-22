import json
import sys
from pathlib import Path

from openai import OpenAI

from .config import AzureConfig

TRANSCRIPT_SUMMARY_PROMPT = """\
Read the Whisper transcript and produce a summary of what was spoken about.

Context:
- Captured by a voice-activated recorder, so speech is non-continuous.
- Whisper output may have run-on text with little punctuation/capitalization. Infer sentence and topic boundaries from context.
- The JSON has shape: {audio, model, language, duration, segments: [{id, start, end, text}, ...]}. start/end are in seconds; convert to HH:MM when referencing time ranges.

Produce a markdown document with these sections:
1. **TL;DR** — one paragraph: what was this person working on or thinking about?
2. **Topics** — group segments into coherent topics. For each: a short heading, an approximate HH:MM range, and 2-5 bullets of what was discussed/decided/asked. Don't summarize segment-by-segment.
3. **Follow-ups & notable items** — recurring themes, decisions, open questions, names of tools/projects mentioned, things to follow up on.

Style: terse, factual, paraphrased — no fluff, no long quotes. Skip filler (false starts, repeated retries with the LLM). Aim for under 600 words.

Output ONLY the markdown summary. Do not narrate what you did."""

DAY_COMBINE_PROMPT = """\
Below are summaries of {count} audio recordings made throughout one day. Combine them into a single coherent day summary.

Produce markdown with:
1. **TL;DR** — one paragraph covering the whole day.
2. **Topics across the day** — merge related topics that span multiple recordings. For each: short heading and 2-5 bullets. Reference recordings by name if useful.
3. **Follow-ups & notable items** — consolidated.

Style: terse, factual, paraphrased. Aim for under 800 words.

Output ONLY the markdown summary. Do not narrate what you did.

---

{input_block}"""


def _build_client(cfg: AzureConfig) -> OpenAI:
    base = cfg.endpoint.rstrip("/")
    return OpenAI(
        api_key=cfg.api_key,
        base_url=f"{base}/v1",
        default_headers={"api-key": cfg.api_key},
    )


def _call_llm(cfg: AzureConfig, prompt: str) -> str:
    client = _build_client(cfg)
    resp = client.chat.completions.create(
        model=cfg.deployment,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=4096,
    )
    text = resp.choices[0].message.content.strip()
    if text.startswith("<think>"):
        end = text.find("</think>")
        if end != -1:
            text = text[end + len("</think>"):].strip()
    return text


def summarize_transcript(
    json_path: Path, cfg: AzureConfig, force: bool = False
) -> str:
    stem = json_path.parent / json_path.stem
    summary_path = stem.with_suffix(".summary.md")

    if summary_path.exists() and not force:
        text = summary_path.read_text().strip()
        print(
            f"summarize-transcript: {summary_path} exists (use --force to redo)",
            file=sys.stderr,
        )
        return text

    result = _call_llm(cfg, TRANSCRIPT_SUMMARY_PROMPT)
    summary_path.write_text(result + "\n")
    print(f"summarize-transcript: wrote {summary_path}", file=sys.stderr)
    return result


def combine_summaries(
    summaries: list[tuple[str, str]], cfg: AzureConfig, output_path: Path | None = None
) -> str:
    input_block = ""
    for name, text in summaries:
        input_block += f"## Recording: {name}\n\n{text}\n\n---\n\n"

    prompt = DAY_COMBINE_PROMPT.format(
        count=len(summaries), input_block=input_block
    )

    result = _call_llm(cfg, prompt)

    if output_path:
        output_path.write_text(result + "\n")
        print(f"summarize-day: wrote {output_path}", file=sys.stderr)
    return result
