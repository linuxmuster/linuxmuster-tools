import os
import typer
from typing_extensions import Annotated

from rich.console import Console
from rich.table import Table
from linuxmusterTools.lmnfile import LMNFile


LINBO_PATH = '/srv/linbo'
console = Console(emoji=False)
app = typer.Typer()

@app.command()
def groups(school: Annotated[str, typer.Option("--school", "-s")] = 'default-school'):
    groups = Table()
    groups.add_column("Groups", style="green")
    groups.add_column("Devices", style="green")
    if school != 'default-school':
        prefix = f'{school}.'
    else:
        prefix = ''

    with LMNFile(f'/etc/linuxmuster/sophomorix/{school}/{prefix}devices.csv', 'r') as f:
        devices = f.read()

    for file in os.listdir(LINBO_PATH):
        path = os.path.join(LINBO_PATH, file)
        if (
            file.startswith('start.conf.')
            and not file.endswith('.vdi')
            and not os.path.islink(path)
            and os.path.isfile(path)
        ):
            group = file.split(".")[-1]
            devices_count = 0
            for device in devices:
                if device['group'] == group:
                    devices_count += 1
            groups.add_row(group, str(devices_count))
    console.print(groups)
