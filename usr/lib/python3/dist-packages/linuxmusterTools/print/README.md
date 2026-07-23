# print

A LaTeX-based printable document generator for [linuxmuster.net](https://www.linuxmuster.net), turning LDAP data into PDFs (student password cards/letters, class lists) through Jinja2-rendered `.tex` templates compiled with `pdflatex`.

`print` exposes two high-level functions — `print_passwords_list` and `print_schoolclass_list` — plus `LatexTemplates` to discover which templates are available on the system.

---

## Requirements

- Python 3.8+
- [`Jinja2`](https://pypi.org/project/Jinja2/)
- A working LaTeX distribution providing `/bin/pdflatex` (e.g. `texlive-latex-base`)
- `linuxmusterTools.ldapconnector` (`LMNLdapReader`) and `linuxmusterTools.lmnconfig` (`SchoolConfig`, `SAMBA_WORKGROUP`)

---

## Usage

```python
from linuxmusterTools.print import print_passwords_list, print_schoolclass_list
```

Both functions look up their data in LDAP, render a Jinja2 `.tex` template, compile it with `pdflatex`, and return the path to the generated PDF. They raise an `Exception` if the requested template is unknown or the schoolclass is missing/empty.

### `print_passwords_list(schoolclass, caller, school='default-school', large=False, template="passwords-DE-1-template.tex")`

Prints the password cards/letters for every student of a schoolclass.

```python
pdf_path = print_passwords_list('7a', 'admin')
# '/var/lib/lmntools/print/admin-passwords-7a.pdf'

pdf_path = print_passwords_list('7a', 'admin', large=True)
# uses the passwordslarge- variant of the template (bigger cards, 18/page instead of 36)
```

| Parameter | Type | Description |
|---|---|---|
| `schoolclass` | `str` | Schoolclass CN (e.g. `'7a'`) |
| `caller` | `str` | Username of the calling user, used as a filename prefix |
| `school` | `str` | Target school in multi-school setups (default: `'default-school'`) |
| `large` | `bool` | Swap `passwords-` for `passwordslarge-` in the template name |
| `template` | `str` | Template filename to use (see [Templates](#templates)) |

### `print_schoolclass_list(schoolclass, caller, school='default_school', template="schoolclass-DE-32-template.tex")`

Prints a sorted list (lastname, firstname) of the students of a schoolclass.

```python
pdf_path = print_schoolclass_list('7a', 'admin')
# '/var/lib/lmntools/print/admin-schoolclass-7a.pdf'
```

| Parameter | Type | Description |
|---|---|---|
| `schoolclass` | `str` | Schoolclass CN |
| `caller` | `str` | Username of the calling user, used as a filename prefix |
| `school` | `str` | Only forwarded to the template `vars`, not to the LDAP lookups |
| `template` | `str` | Template filename to use |

> `print_schoolclasses_list(schoolclasses, caller, school='default_school', template="datalist-DE-32-template.tex")` (multiple schoolclasses in one document) is declared but not yet implemented — it currently does nothing.

---

## Output

Generated files are written to `/var/lib/lmntools/print/`, named `{caller}-{type}-{schoolclass}.pdf` (e.g. `admin-passwords-7a.pdf`, `admin-schoolclass-7a.pdf`). The intermediate `.tex` file is kept next to the PDF; auxiliary LaTeX files (`.log`, `.aux`, `.toc`, `.dvi`, `.ps`, `.pre`, `.thm`, `.pyg`) are deleted after compilation.

> Template variables are only sanitized for LaTeX by escaping `_` to `\_`; other special characters (`%`, `&`, `#`, `\`, `{`, `}`) are passed through as-is.

---

## Templates

`LatexTemplates` discovers `.tex` templates from three locations, matched against `LMNTOOLS_TEMPLATES_DIR`/`SOPHOMORIX_TEMPLATES_DIR` and per-school directories:

| Source | Directory | Filename pattern |
|---|---|---|
| lmntools package | `/var/lib/lmntools/templates/` | `<type>-<lang>-<count>-template.tex` |
| sophomorix package | `/usr/share/sophomorix/lang/latex/templates/` | `<type>-<lang>-<count>-template.tex` |
| school-defined | `/etc/linuxmuster/sophomorix/<school>/latex-templates/` | `<school>.<type>-<lang>-<count>-template.tex` |

Where `type` is `passwords`, `passwordslarge`, `schoolclass` or `datalist` (`datalist` is normalized to `passwords` internally), `lang` is an uppercase language code (`DE`, `EN`, `FR`, ...), and `count` is the number of entries rendered per page.

```python
from linuxmusterTools.print.templates import LatexTemplates

templates = LatexTemplates().templates
# {'passwords-DE-1-template.tex': LatexTemplate(count=1, filename='...', lang='DE', type='passwords', ...), ...}

print(LatexTemplates())   # human-readable table: Filename | Count | Lang | Type | School | Package
```

Templates shipped by default:

| Filename | Type | Lang | Count |
|---|---|---|---|
| `passwords-DE-1-template.tex` | passwords | DE | 1 |
| `passwords-DE-36-template.tex` | passwords | DE | 36 |
| `passwords-EN-36-template.tex` | passwords | EN | 36 |
| `passwordslarge-DE-36-template.tex` | passwordslarge | DE | 36 |
| `passwordslarge-EN-36-template.tex` | passwordslarge | EN | 36 |
| `passwordslarge-FR-36-template.tex` | passwordslarge | FR | 36 |
| `schoolclass-DE-32-template.tex` | schoolclass | DE | 32 |
| `schoolclass-EN-32-template.tex` | schoolclass | EN | 32 |
| `schoolclass-FR-32-template.tex` | schoolclass | FR | 32 |

Templates receive a `datablocks` list (data split into pages of `count` entries) plus the `vars` passed by the caller — e.g. `passwords-*` templates render `student['lastname']`, `student['firstname']`, `student['login']`, `student['password']`, `student['schoolclass']`, `school_longname`, `domain`, `teachermembers`, and the sophomorix `URLSTART_PRINT`/`URLSCHUKO_PRINT`/`URLMAIL_PRINT`/`URLMOODLE_PRINT` config values (and their `_comment_print` counterparts).
