import typer

from rich.console import Console
from rich.table import Table
from linuxmusterTools.sambaTool import GPOS


console = Console(emoji=False)
app = typer.Typer()

@app.command()
def gpos():
    gpos = Table()
    gpos.add_column("Name", style="green")
    gpos.add_column("GPO", style="cyan")
    gpos.add_column("Path", style="magenta")

    for name, details in GPOS.items():
        gpos.add_row(name, details['gpo'], details['path'])
    console.print(gpos)