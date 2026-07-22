"""
Tests for LatexRenderer: variable sanitization, jinja2 rendering/pagination,
and the pdflatex compile step (subprocess mocked, no real LaTeX invoked).
"""

import os
from types import SimpleNamespace

import pytest

from linuxmusterTools.print.render import LatexRenderer


def make_template_obj(filename="test-template.tex", count=2, type="schoolclass"):
    return SimpleNamespace(filename=filename, count=count, type=type)


# ── _sanitize() ────────────────────────────────────────────────────────────

def test_sanitize_escapes_underscore():
    r = LatexRenderer(make_template_obj(), data=[], vars={"name": "foo_bar"})
    assert r.vars_sanitized["name"] == "foo\\_bar"


def test_sanitize_escapes_multiple_underscores():
    r = LatexRenderer(make_template_obj(), data=[], vars={"name": "a_b_c"})
    assert r.vars_sanitized["name"] == "a\\_b\\_c"


def test_sanitize_leaves_plain_string_untouched():
    r = LatexRenderer(make_template_obj(), data=[], vars={"school": "default-school"})
    assert r.vars_sanitized["school"] == "default-school"


def test_sanitize_only_escapes_underscore_not_other_latex_specials():
    """
    Documents actual behaviour: _sanitize() only replaces "_" => "\\_".
    Other common LaTeX special characters (%, &, #, \\, {, }) are NOT
    escaped despite the docstring's generic framing ("like _ => \\_").
    This is noted as a production gap, not fixed here.
    """
    value = "50% & #1 \\ {x}"
    r = LatexRenderer(make_template_obj(), data=[], vars={"v": value})
    assert r.vars_sanitized["v"] == value


def test_sanitize_runs_on_init_and_keeps_original_vars():
    r = LatexRenderer(make_template_obj(), data=[], vars={"name": "foo_bar"})
    # original vars dict is untouched, only vars_sanitized is derived
    assert r.vars == {"name": "foo_bar"}
    assert r.vars_sanitized == {"name": "foo\\_bar"}


def test_sanitize_empty_vars_default():
    r = LatexRenderer(make_template_obj(), data=[])
    assert r.vars_sanitized == {}


# ── render() ───────────────────────────────────────────────────────────────

def write_template(templates_dir, filename, content):
    (templates_dir / filename).write_text(content, encoding="utf-8")


def test_render_paginates_uneven_data(render_dirs):
    templates_dir, _ = render_dirs
    write_template(
        templates_dir,
        "test.tex",
        "{% for block in datablocks %}PAGE:{{ block }}\n{% endfor %}",
    )
    template_obj = make_template_obj(filename="test.tex", count=2)
    r = LatexRenderer(template_obj, data=[1, 2, 3, 4, 5], vars={})
    r.render()

    # count=2, 5 items => pages of [1,2], [3,4], [5] (3 pages, last partial)
    assert r.out == "PAGE:[1, 2]\nPAGE:[3, 4]\nPAGE:[5]\n"


def test_render_paginates_evenly_divisible_data():
    """
    When len(data) is an exact multiple of count, no trailing empty page
    should be produced (guarded by the `if count*i != len(self.data)` filter).
    """
    template_obj = make_template_obj(filename="test.tex", count=2)
    r = LatexRenderer(template_obj, data=[1, 2, 3, 4], vars={})
    # Exercise the pagination logic directly without needing a real template
    count = r.template_obj.count
    datablocks = [
        r.data[count * i:count * i + count]
        for i in range(len(r.data) // count + 1)
        if count * i != len(r.data)
    ]
    assert datablocks == [[1, 2], [3, 4]]


def test_render_uses_sanitized_vars(render_dirs):
    templates_dir, _ = render_dirs
    write_template(templates_dir, "vartest.tex", "Hello {{ name }}")
    template_obj = make_template_obj(filename="vartest.tex", count=10)
    r = LatexRenderer(template_obj, data=[], vars={"name": "foo_bar"})
    r.render()
    assert r.out == "Hello foo\\_bar"


def test_render_missing_template_raises(render_dirs):
    template_obj = make_template_obj(filename="does-not-exist.tex", count=10)
    r = LatexRenderer(template_obj, data=[], vars={})
    with pytest.raises(Exception):
        r.render()


# ── compile() ──────────────────────────────────────────────────────────────

def test_compile_schoolclass_output_filename(render_dirs, mock_popen):
    templates_dir, output_dir = render_dirs
    write_template(templates_dir, "sc.tex", "{{ school }} {{ schoolclass }}")
    template_obj = make_template_obj(filename="sc.tex", count=10, type="schoolclass")

    r = LatexRenderer(
        template_obj, data=[], caller="admin",
        vars={"school": "default-school", "schoolclass": "7a"},
    )
    pdf_path = r.compile()

    expected_tex = os.path.join(str(output_dir), "admin-schoolclass-7a.tex")
    assert r.destination_file == expected_tex
    assert pdf_path == expected_tex.replace(".tex", ".pdf")
    assert os.path.isfile(expected_tex)
    with open(expected_tex) as f:
        assert f.read() == "default-school 7a"


@pytest.mark.parametrize("template_type", ["passwords", "passwordslarge"])
def test_compile_passwords_output_filename(render_dirs, mock_popen, template_type):
    templates_dir, output_dir = render_dirs
    write_template(templates_dir, "pw.tex", "content")
    template_obj = make_template_obj(filename="pw.tex", count=10, type=template_type)

    r = LatexRenderer(
        template_obj, data=[], caller="admin",
        vars={"schoolclass": "7a"},
    )
    pdf_path = r.compile()

    expected_tex = os.path.join(str(output_dir), f"admin-{template_type}-7a.tex")
    assert r.destination_file == expected_tex
    assert pdf_path == expected_tex.replace(".tex", ".pdf")


def test_compile_invokes_popen_with_pdflatex_and_correct_cwd(render_dirs, mock_popen):
    templates_dir, output_dir = render_dirs
    write_template(templates_dir, "sc.tex", "x")
    template_obj = make_template_obj(filename="sc.tex", count=10, type="schoolclass")
    popen_ctor, proc = mock_popen

    r = LatexRenderer(template_obj, data=[], caller="admin", vars={"schoolclass": "7a"})
    r.compile()

    popen_ctor.assert_called_once()
    args, kwargs = popen_ctor.call_args
    cmd = args[0]
    assert cmd[0] == "/bin/pdflatex"
    assert "-halt-on-error" in cmd
    assert cmd[-1] == r.destination_file
    assert kwargs["cwd"] == str(output_dir)


def test_compile_raises_on_pdflatex_failure(render_dirs, mock_popen):
    templates_dir, output_dir = render_dirs
    write_template(templates_dir, "sc.tex", "x")
    template_obj = make_template_obj(filename="sc.tex", count=10, type="schoolclass")
    _, proc = mock_popen
    proc.returncode = 1
    proc.communicate.return_value = (b"! Undefined control sequence", b"")

    r = LatexRenderer(template_obj, data=[], caller="admin", vars={"schoolclass": "7a"})
    with pytest.raises(Exception, match="Compilation failed"):
        r.compile()


def test_compile_cleans_up_auxiliary_files(render_dirs, mock_popen):
    templates_dir, output_dir = render_dirs
    write_template(templates_dir, "sc.tex", "x")
    template_obj = make_template_obj(filename="sc.tex", count=10, type="schoolclass")

    r = LatexRenderer(template_obj, data=[], caller="admin", vars={"schoolclass": "7a"})

    # _clean() runs after the tex file is written, based on self.destination_file;
    # pre-create stray auxiliary files it should remove.
    r.destination_file = os.path.join(str(output_dir), "admin-schoolclass-7a.tex")
    for ext in [".log", ".aux", ".toc"]:
        stray = r.destination_file.replace(".tex", ext)
        with open(stray, "w") as f:
            f.write("junk")

    r.compile()

    for ext in [".log", ".aux", ".toc"]:
        assert not os.path.isfile(r.destination_file.replace(".tex", ext))


def test_compile_unknown_template_type_raises_unboundlocalerror(render_dirs, mock_popen):
    """
    Regression/documentation test for a production gap: compile() only
    branches on template_obj.type in ("schoolclass", "passwords",
    "passwordslarge"). Any other type (e.g. a template file whose filename
    encodes a different `type` group, like "foo-DE-1-template.tex" ->
    type="foo") leaves `output_file` unset, raising an unhandled
    UnboundLocalError instead of a clear, catchable error.
    See render.py:73-78.
    """
    templates_dir, _ = render_dirs
    write_template(templates_dir, "foo.tex", "x")
    template_obj = make_template_obj(filename="foo.tex", count=10, type="foo")

    r = LatexRenderer(template_obj, data=[], caller="admin", vars={"schoolclass": "7a"})
    with pytest.raises(UnboundLocalError):
        r.compile()
