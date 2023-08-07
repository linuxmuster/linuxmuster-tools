import os
import typer

from rich.console import Console
from rich.table import Table
from linuxmusterTools.sambaTool import GPOS


LINBO_PATH = '/srv/linbo'
console = Console(emoji=False)
app = typer.Typer()

@app.command()
def groups():
    groups = Table()
    groups.add_column("Groups", style="green")

    for file in os.listdir(LINBO_PATH):
        path = os.path.join(LINBO_PATH, file)
        if (
            file.startswith('start.conf.')
            and not file.endswith('.vdi')
            and not os.path.islink(path)
            and os.path.isfile(path)
        ):
            groups.add_row(file.split(".")[-1])
    console.print(groups)
