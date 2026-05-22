import sys
from pathlib import Path

import click

from .config import AzureConfig
from .summarize import combine_summaries, summarize_transcript
from .transcribe import collect_audio_files, transcribe_file


@click.group()
def cli():
    """Transcribe audio recordings with faster-whisper and summarize via Azure OpenAI."""


@cli.command()
@click.argument("audio", type=click.Path(exists=True))
@click.option("--model", default="large-v3", help="faster-whisper model name")
@click.option("--language", default="en", help="Language code or 'auto'")
@click.option(
    "--device", default="cuda", type=click.Choice(["cuda", "cpu"])
)
@click.option("--compute-type", default=None, help="float16/int8_float16/int8 etc.")
@click.option("--beam-size", default=5, type=int)
@click.option("--out-dir", default=None, type=click.Path())
@click.option("--force", is_flag=True, help="Redo if JSON exists")
def transcribe(
    audio, model, language, device, compute_type, beam_size, out_dir, force
):
    """Transcribe an audio file with faster-whisper."""
    out = transcribe_file(
        Path(audio),
        model_name=model,
        language=language,
        device=device,
        compute_type=compute_type,
        beam_size=beam_size,
        out_dir=Path(out_dir) if out_dir else None,
        force=force,
    )
    click.echo(out["json"])


@cli.command()
@click.argument("json_file", type=click.Path(exists=True))
@click.option("--force", is_flag=True, help="Redo if summary exists")
def summarize(json_file, force):
    """Summarize a Whisper transcript JSON via Azure AI Foundry."""
    cfg = AzureConfig()
    if not cfg.is_configured():
        click.echo(
            "error: AZURE_FOUNDRY_ENDPOINT and AZURE_FOUNDRY_API_KEY must be set",
            err=True,
        )
        sys.exit(1)
    result = summarize_transcript(Path(json_file), cfg, force=force)
    click.echo(result)


@cli.command()
@click.argument("paths", nargs=-1, required=True)
@click.option("--force", is_flag=True, help="Redo existing outputs")
def run(paths, force):
    """Transcribe and summarize audio files (the full pipeline)."""
    cfg = AzureConfig()
    if not cfg.is_configured():
        click.echo(
            "error: AZURE_FOUNDRY_ENDPOINT and AZURE_FOUNDRY_API_KEY must be set",
            err=True,
        )
        sys.exit(1)

    files = collect_audio_files(list(paths))
    if not files:
        click.echo("summarize-recording: no audio files to process", err=True)
        sys.exit(1)

    click.echo(
        f"summarize-recording: processing {len(files)} file(s)", err=True
    )

    summaries: list[tuple[str, str]] = []
    for f in files:
        click.echo(f"\n===== {f} =====", err=True)
        out = transcribe_file(
            f,
            force=force,
        )
        text = summarize_transcript(
            Path(out["json"]), cfg, force=force
        )
        summaries.append((f.stem, text))

    if len(summaries) == 1:
        click.echo(summaries[0][1])
        return

    combo_dir = files[0].parent
    combo_path = combo_dir / "combined-summary.md"
    click.echo(
        f"\n===== combining {len(summaries)} summaries -> {combo_path} =====",
        err=True,
    )
    result = combine_summaries(summaries, cfg, output_path=combo_path)
    click.echo(result)


@cli.command()
@click.argument("paths", nargs=-1, required=True)
@click.option("--force", is_flag=True, help="Redo existing outputs")
def combine(paths, force):
    """Combine existing .summary.md files into a combined summary."""
    cfg = AzureConfig()
    if not cfg.is_configured():
        click.echo(
            "error: AZURE_FOUNDRY_ENDPOINT and AZURE_FOUNDRY_API_KEY must be set",
            err=True,
        )
        sys.exit(1)

    summaries: list[tuple[str, str]] = []
    for p in paths:
        pp = Path(p)
        if pp.is_dir():
            for sf in sorted(pp.glob("*.summary.md")):
                summaries.append(
                    (sf.stem.replace(".summary", ""), sf.read_text().strip())
                )
        elif pp.is_file():
            summaries.append((pp.stem, pp.read_text().strip()))
        else:
            click.echo(
                f"summarize-recording: skipping (not a file or dir): {pp}", err=True
            )

    if not summaries:
        click.echo("summarize-recording: no summary files found", err=True)
        sys.exit(1)

    combo_dir = Path(paths[0]).parent if len(paths) == 1 else Path.cwd()
    combo_path = combo_dir / "combined-summary.md"
    click.echo(
        f"\n===== combining {len(summaries)} summaries -> {combo_path} =====",
        err=True,
    )
    result = combine_summaries(summaries, cfg, output_path=combo_path)
    click.echo(result)


if __name__ == "__main__":
    cli()
