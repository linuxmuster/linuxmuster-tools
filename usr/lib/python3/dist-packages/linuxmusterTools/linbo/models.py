from dataclasses import dataclass


@dataclass
class Partition:
    Bootable: bool
    Dev: str
    FSType: str
    Id: int
    Label: str
    Size: str

@dataclass
class OS:
    Append: str
    BaseImage: str
    DefaultAction: str
    Description: str
    IconName: str
    Initrd: str
    Kernel: str
    Name: str
    Root: str
    Autostart: bool = False
    AutostartTimeout: int = 5
    NewEnabled: bool = True
    StartEnabled: bool = True
    SyncEnabled: bool = True

@dataclass
class Linbo:
    Cache: str
    Group: str
    KernelOptions: str
    AutoFormat: bool = False
    AutoInitCache: bool = False
    AutoPartition: bool = False
    GuiDisabled: bool = False
    Locale: str = 'de-de'
    RootTimeout: int = 600
    DownloadType: str = 'torrent'
    UseMinimalLayout: bool = False

@dataclass
class LinboConfig:
    LINBO: Linbo
    Partitions: list
    OS: list