"""Rich rendering helpers for young chat."""

from __future__ import annotations

from rich.align import Align
from rich.console import Console, Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text


class ChatRenderer:
    def __init__(self, console: Console | None = None):
        self.console = console or Console()

    def render_welcome(self, *, style_name: str) -> None:
        body = Group(
            Align.center(Text("young", style="bold #1B365D")),
            Text("Evidence-driven personal investment research and review CLI.", style="white"),
            Text("Research only: No auto-trading. No brokerage connection.", style="bold yellow"),
            Text(""),
            Text("Workflow Steps", style="bold cyan"),
            Text("Evidence Pack → Lens Research → Trading Plan Draft → Risk Review → Portfolio Final Opinion"),
            Text(""),
            Text("Common Commands", style="bold cyan"),
            Text("/stock <symbol> [--llm] [--lens ...]"),
            Text("/fund <code> [--llm] [--lens ...]"),
            Text("/daily [--llm] [--lens ...]"),
            Text("/help"),
            Text("/exit"),
            Text(""),
            Text(f"Current style: {style_name}    Change with /style set <name>", style="dim"),
        )
        panel = Panel(
            body,
            title="[bold]Welcome to young[/]",
            subtitle="Evidence-driven investment research CLI",
            expand=False,
            padding=(1, 2),
            border_style="#1B365D",
        )
        self.console.print(Align.center(panel))

    def text(self, message: str) -> None:
        self.console.print(Panel(Text(str(message)), expand=True, border_style="bright_black"))

    def slash(self, message: str) -> None:
        self.text(message)

    def system(self, message: str) -> None:
        self.console.print(Panel(Text(str(message), style="cyan"), expand=True, border_style="cyan"))

    def error(self, message: str) -> None:
        self.console.print(Panel(Text(str(message), style="red"), expand=True, border_style="red"))

    def markdown(self, message: str) -> None:
        self.console.print(Panel(Markdown(str(message)), expand=True, border_style="#1B365D"))
