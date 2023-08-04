#! /bin/python3

import typer
import subprocess

from rich.console import Console
from rich.table import Table

console = Console()

app = typer.Typer()

@app.command()
def hello(name: str):
    print(f"Hello {name}")

@app.command()
def goodbye(name: str, formal: bool = False):
    if formal:
        print(f"Goodbye Ms. {name}. Have a good day.")
    else:
        print(f"Bye {name}!")

@app.command()
def version():
    packages = Table("Package", "Version")
    command = "dpkg -l | grep 'linuxmuster\|sophomorix'"
    p = subprocess.Popen(command, shell=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    for package in p.stdout.readlines():
        details = package.decode().split()
        name = details[1]
        version = details[2]
        packages.add_row(name, version)
    console.print(packages)

if __name__ == "__main__":
    app()
