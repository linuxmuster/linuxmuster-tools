import os
import typer
from typing_extensions import Annotated

from rich.console import Console
from rich.table import Table
from linuxmusterTools.ldapconnector import LMNLdapReader as lr


console = Console(emoji=False)
app = typer.Typer()

@app.command()
def ls(
        school: Annotated[str, typer.Option("--school", "-s")] = 'default-school',
        filter_str: Annotated[str, typer.Option("--filter", "-f")] = '',
        admins: Annotated[bool, typer.Option("--admins", "-a")] = False,
        teachers: Annotated[bool, typer.Option("--teachers", "-t")] = False,
        students: Annotated[bool, typer.Option("--students", "-u")] = False,
        ):
    if school != 'default-school':
        prefix = f'{school}.'
    else:
        prefix = ''
   
    filter_str = filter_str.lower()

    if admins:
        url = '/users/search/admins/'
    elif teachers:
        url = '/users/search/teacher/'
    elif students:
        url = '/users/search/student/'
    else:
        url = '/users'

    users_data = lr.get(url, attributes=[
        'displayName', 
        'sn', 
        'givenName', 
        'sAMAccountName', 
        'sophomorixAdminClass', 
        'sophomorixRole', 
        'sophomorixStatus']
    )

    users_data = list(filter(
        lambda u: filter_str in u['displayName'].lower() or filter_str in u['sAMAccountName'].lower() or filter_str in u['sophomorixAdminClass'].lower(), 
        users_data
    ))

    users_data = sorted(users_data, key=lambda u: (u['sophomorixRole'], u['sn'], u['givenName']))

    users = Table(title=f"{len(users_data)} users")
    users.add_column("Lastname", style="cyan")
    users.add_column("Firstname", style="green")
    users.add_column("Login", style="magenta")
    users.add_column("Adminclass", style="magenta")
    users.add_column("Role", style="magenta")
    users.add_column("Status", style="magenta")
    for user in users_data:
        users.add_row(user['sn'], user['givenName'], user['sAMAccountName'], user['sophomorixAdminClass'], user['sophomorixRole'], user['sophomorixStatus'])
    console.print(users)

