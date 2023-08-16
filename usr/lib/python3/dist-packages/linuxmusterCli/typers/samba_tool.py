import typer
from typing_extensions import Annotated

from rich.console import Console
from rich.table import Table
from linuxmusterTools.sambaTool import GPOManager

gpomgr = GPOManager()
GPOS = gpomgr.gpos

console = Console(emoji=False)
app = typer.Typer()

@app.command()
def gpos():
    gpos = Table()
    gpos.add_column("Name", style="green")
    gpos.add_column("GPO", style="cyan")
    gpos.add_column("Path", style="magenta")

    for name, details in GPOS.items():
        gpos.add_row(name, details.gpo, details.path)
    console.print(gpos)

@app.command()
def drives(school: Annotated[str, typer.Option("--school", "-s")] = 'default-school'):
    drives = Table()
    drives.add_column("Name", style="green")
    drives.add_column("Letter", style="cyan")
    drives.add_column("Use letter", style="cyan")
    drives.add_column("Label", style="magenta")
    drives.add_column("Disable", style="magenta")

    for name, details in GPOS[f"sophomorix:school:{school}"].drives.drives_dict.items():
        drives.add_row(
                name, 
                details['letter'], 
                str(details['userLetter']), 
                details['label'], 
                str(details['disabled'])
        )
    console.print(drives)
