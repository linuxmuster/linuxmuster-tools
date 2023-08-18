#! /bin/python3

import typer
import subprocess

from rich.console import Console
from rich.table import Table
from typers import samba_tool, linbo, devices


console = Console()
app = typer.Typer()
app.add_typer(samba_tool.app, name='samba')
app.add_typer(linbo.app, name='linbo')
app.add_typer(devices.app, name='devices')

@app.command()
def version():
    packages = Table()
    packages.add_column("Status", style="green")
    packages.add_column("Packages", style="cyan")
    packages.add_column("Version", style="magenta")

    command = "dpkg -l | grep 'linuxmuster\|sophomorix'"
    p = subprocess.Popen(command, shell=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    for package in p.stdout.readlines():
        details = package.decode().split()
        status, name, version  = details[:3]
        packages.add_row(status, name, version)
    console.print(packages)

if __name__ == "__main__":
    app()
