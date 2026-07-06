"""Rich-based terminal UI with paginated project listing."""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from dcp.config import get_settings
from dcp.cortex import StageInferenceEngine
from dcp.database import EventSourcingDB
from dcp.sentry import ProjectDiscovery


def run_tui(scan_path: str = ".", page_size: int = 15) -> None:
    console = Console()
    settings = get_settings()
    db = EventSourcingDB(settings.db_path)
    try:
        console.print(Panel("[bold]Developer Control Plane[/bold] — context fabric",
                            border_style="blue"))
        ProjectDiscovery(db).scan(scan_path)
        engine = StageInferenceEngine(db, settings.confidence_half_life_days)

        page = 1
        while True:
            projects, total = db.list_projects(
                limit=page_size, offset=(page - 1) * page_size
            )
            pages = max(1, -(-total // page_size))
            table = Table(title=f"Projects — page {page}/{pages} ({total} total)")
            table.add_column("Path", style="dim", overflow="fold")
            table.add_column("Type")
            table.add_column("Stage")
            table.add_column("Conf.", justify="right")
            for project in projects:
                stage = engine.infer_stage(project.path)
                table.add_row(
                    project.path, project.type, stage.stage,
                    f"{stage.confidence:.0%}",
                )
            console.print(table)
            if pages <= 1:
                break
            move = console.input("[n]ext / [p]rev / [q]uit > ").strip().lower()
            if move == "n" and page < pages:
                page += 1
            elif move == "p" and page > 1:
                page -= 1
            else:
                break
    finally:
        db.close()


if __name__ == "__main__":
    run_tui()
