import pytest

from linuxmusterTools.samba_util.drives import Drive, DriveManager


DRIVES_XML_TEMPLATE = """<?xml version="1.0" encoding="utf-8"?>
<Drives clsid="{{8FDDCC1A-0C3C-43cd-A6B4-71A6DF20DA8C}}">
    <Drive clsid="{{935D1B74-9CB8-4e3c-9914-7DD559B7A417}}" name="H:" image="2" disabled="0">
        <Properties action="U" path="\\\\server\\home" label="Home" letter="H" useLetter="0"/>
        <Filters>
            <FilterGroup name="DOMAIN\\teachers" bool="AND" not="0"/>
        </Filters>
    </Drive>
    <Drive clsid="{{a1111111-1111-1111-1111-111111111111}}" name="Z:" image="2" disabled="1">
        <Properties action="U" path="\\\\server\\shared\\Zshare" label="Shared" letter="Z" useLetter="1"/>
    </Drive>
</Drives>
"""

EMPTY_DRIVE_XML = """<?xml version="1.0" encoding="utf-8"?>
<Drives clsid="{8FDDCC1A-0C3C-43cd-A6B4-71A6DF20DA8C}">
    <Drive clsid="{111}" name="Y:">
    </Drive>
</Drives>
"""


def _make_policy_dir(tmp_path, xml_content, policy_name="{GUID-1234}"):
    policy_path = tmp_path / policy_name
    drives_dir = policy_path / "User" / "Preferences" / "Drives"
    drives_dir.mkdir(parents=True)
    (drives_dir / "Drives.xml").write_text(xml_content, encoding="utf-8")
    return policy_path


# --- Drive dataclass ---------------------------------------------------

def test_drive_id_derived_from_windows_path():
    drive = Drive(
        disabled=False,
        filters={},
        label="Home",
        letter="H",
        properties={"path": "\\\\server\\share\\HomeShare"},
        userLetter=False,
    )
    assert drive.id == "HomeShare"


def test_drive_id_is_none_when_path_missing():
    drive = Drive(
        disabled=False,
        filters={},
        label="Home",
        letter="H",
        properties={"path": None},
        userLetter=False,
    )
    assert drive.id is None


def test_drive_id_ignores_windows_path_without_backslash():
    drive = Drive(
        disabled=False,
        filters={},
        label="Home",
        letter="H",
        properties={"path": "justaname"},
        userLetter=False,
    )
    # split('\\')[-1] on a string with no backslash just returns the string
    assert drive.id == "justaname"


# --- DriveManager: policy path handling ---------------------------------

def test_invalid_policy_path_type_is_handled_gracefully():
    manager = DriveManager(None)

    assert manager.path == ''
    assert manager.drives == []


def test_missing_drives_xml_yields_no_drives(tmp_path):
    policy_path = tmp_path / "{GUID-empty}"
    policy_path.mkdir()

    manager = DriveManager(str(policy_path))

    assert manager.drives == []
    assert manager.usedLetters == []


def test_malformed_xml_raises(tmp_path):
    policy_path = _make_policy_dir(tmp_path, "<Drives><Drive>", policy_name="{GUID-bad}")

    with pytest.raises(Exception, match="syntax error"):
        DriveManager(str(policy_path))


# --- DriveManager: parsing -----------------------------------------------

def test_load_parses_drives_properties_and_filters(tmp_path):
    policy_path = _make_policy_dir(tmp_path, DRIVES_XML_TEMPLATE)

    manager = DriveManager(str(policy_path))

    assert manager.policy == "{GUID-1234}"
    assert len(manager.drives) == 2

    home, shared = manager.drives

    assert home.disabled is False
    assert home.label == "Home"
    assert home.letter == "H"
    assert home.userLetter is False
    assert home.properties["path"] == "\\\\server\\home"
    assert home.id == "home"
    assert home.filters == {"teachers": {"bool": "AND", "negation": False}}

    assert shared.disabled is True
    assert shared.userLetter is True
    assert shared.id == "Zshare"
    assert shared.filters == {}

    assert manager.usedLetters == ["H", "Z"]


def test_load_raises_keyerror_when_drive_has_no_properties_node(tmp_path):
    """
    Known bug: `_parseProperties` returns `{}` (not per-key defaults) when a
    `<Drive>` has no `<Properties>` child at all, since its `.get(...,
    default)` calls only run inside the `for prop in
    drive.findall('Properties')` loop. `DriveManager.load()` then indexes
    `properties['letter']` unconditionally (drives.py:82), which raises
    KeyError instead of degrading gracefully like a `<Drive>` with a present
    but attribute-sparse `<Properties>` node would.
    """
    policy_path = _make_policy_dir(tmp_path, EMPTY_DRIVE_XML, policy_name="{GUID-empty-props}")

    with pytest.raises(KeyError, match="letter"):
        DriveManager(str(policy_path))


def test_load_defaults_when_properties_node_is_attribute_sparse(tmp_path):
    """
    Unlike a fully-absent <Properties> node (see the KeyError test above), a
    present-but-attribute-sparse <Properties> node degrades gracefully
    because each attribute is read via `.get(name, default)`.
    """
    xml = """<?xml version="1.0" encoding="utf-8"?>
<Drives>
    <Drive>
        <Properties/>
    </Drive>
</Drives>
"""
    policy_path = _make_policy_dir(tmp_path, xml, policy_name="{GUID-sparse-props}")

    manager = DriveManager(str(policy_path))

    assert len(manager.drives) == 1
    drive = manager.drives[0]
    assert drive.disabled is False
    assert drive.filters == {}
    assert drive.label == 'Unknown'
    assert drive.letter == ''
    assert drive.properties == {
        'useLetter': False, 'letter': '', 'label': 'Unknown', 'path': None,
    }
    assert drive.userLetter is False
    assert drive.id is None


def test_filter_negation_flag(tmp_path):
    xml = """<?xml version="1.0" encoding="utf-8"?>
<Drives>
    <Drive disabled="0">
        <Properties path="\\\\server\\share" label="Foo" letter="F" useLetter="0"/>
        <Filters>
            <FilterGroup name="DOMAIN\\students" bool="AND" not="1"/>
        </Filters>
    </Drive>
</Drives>
"""
    policy_path = _make_policy_dir(tmp_path, xml, policy_name="{GUID-negation}")

    manager = DriveManager(str(policy_path))

    assert manager.drives[0].filters == {"students": {"bool": "AND", "negation": True}}


def test_aslist_returns_plain_dicts(tmp_path):
    policy_path = _make_policy_dir(tmp_path, DRIVES_XML_TEMPLATE)
    manager = DriveManager(str(policy_path))

    as_list = manager.aslist()

    assert isinstance(as_list, list)
    assert all(isinstance(d, dict) for d in as_list)
    assert as_list[0]["label"] == "Home"
    assert as_list[0]["id"] == "home"


def test_save_updates_matching_drives_and_reloads(tmp_path):
    policy_path = _make_policy_dir(tmp_path, DRIVES_XML_TEMPLATE)
    manager = DriveManager(str(policy_path))

    content = manager.aslist()
    # Flip disabled state and change the drive letter for "Home"
    content[0]["disabled"] = True
    content[0]["properties"]["letter"] = "K"
    content[0]["properties"]["useLetter"] = True

    manager.save(content)

    assert (policy_path / "User" / "Preferences" / "Drives" / "Drives.xml.bak").exists()
    reloaded_home = manager.drives[0]
    assert reloaded_home.disabled is True
    assert reloaded_home.properties["letter"] == "K"
    assert reloaded_home.properties["useLetter"] is True
