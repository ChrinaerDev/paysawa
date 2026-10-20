"""All terminal output goes through here (rich). Keeps the rest of the CLI free of formatting code."""
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

console = Console()


def say(message: str = "") -> None:
    console.print(message)


def ok(message: str) -> None:
    console.print(f"[green]OK[/green]   {message}")


def warn(message: str) -> None:
    console.print(f"[yellow]NOTE[/yellow] {message}")


def err(message: str) -> None:
    console.print(f"[red]FAIL[/red] {message}")


def raw(text: str) -> None:
    """Prints text exactly as is, never wrapped (so keys and URLs can be copied cleanly)."""
    console.print(text, soft_wrap=True, markup=False, highlight=False)


def panel(body: str, title: str | None = None, style: str = "white") -> None:
    console.print(Panel(body, title=title, border_style=style, box=box.ROUNDED, expand=True))


def tip(body: str) -> None:
    panel(body, title="Next thing to try", style="cyan")


def table(title: str, columns: list[str], rows: list[list[str]]) -> None:
    t = Table(title=title, box=box.SIMPLE_HEAVY, header_style="bold")
    for column in columns:
        t.add_column(column)
    for row in rows:
        t.add_row(*[str(cell) for cell in row])
    console.print(t)


def ask(prompt: str, default: str | None = None, password: bool = False, choices: list[str] | None = None) -> str:
    kwargs = {"password": password}
    if choices:
        kwargs["choices"] = choices
    if default is not None:
        kwargs["default"] = default
    return Prompt.ask(prompt, **kwargs)


def confirm(prompt: str, default: bool = False) -> bool:
    return Confirm.ask(prompt, default=default)


def spinner(message: str):
    return console.status(message)


def clear() -> None:
    console.clear()


def pause() -> None:
    Prompt.ask("[dim]Press Enter to continue[/dim]", default="", show_default=False)
