import os
import typer
from typing_extensions import Annotated

from rich.console import Console
from rich.table import Table
from linuxmusterTools.lmnfile import LMNFile
from linuxmusterTools.linbo import LinboImageManager


LINBO_PATH = '/srv/linbo'
console = Console(emoji=False)
app = typer.Typer()
lim = LinboImageManager()

@app.command()
def groups(school: Annotated[str, typer.Option("--school", "-s")] = 'default-school'):
    groups = Table()
    groups.add_column("Groups", style="green")
    groups.add_column("Devices", style="cyan")
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

@app.command()
def images():
    images = Table(show_lines=True)
    images.add_column("Name", style="green")
    images.add_column("Size (MiB)", style="cyan")
    images.add_column("Backups", style="magenta")
    images.add_column("Differential image", style="cyan")
    # images.add_column("Used in groups", style="cyan")
    
    for name,group in lim.groups.items():
        size = str(round(group.base.size / 1024 / 1024))
        diff = "No"
        if group.diff_image:
            diff_size = round(group.diff_image.size / 1024 / 1024)
            diff = f"Yes ({diff_size} MiB)"
        images.add_row(name, size, '\n'.join(group.backups.keys()), diff)

    console.print(images)
