import inspect
import logging
from dataclasses import dataclass


@dataclass
class Partition:
    Bootable: bool
    Dev: str
    FSType: str
    Id: int
    Label: str
    Size: str

    @classmethod
    def from_dict(cls, kwargs):
        endkwargs = {}
        config = kwargs['config']
        del kwargs['config']
        for k, v in kwargs.items():
            for p in inspect.signature(cls).parameters:
                if k.lower() == p.lower():
                    endkwargs[p] = v
                    break
            else:
                logging.warning(f"Parameter {k} is not an Partition parameter in {config}.")
        return cls(**endkwargs)

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

    @classmethod
    def from_dict(cls, kwargs):
        endkwargs = {}
        config = kwargs['config']
        del kwargs['config']
        for k, v in kwargs.items():
            for p in inspect.signature(cls).parameters:
                if k.lower() == p.lower():
                    endkwargs[p] = v
                    break
            else:
                logging.warning(f"Parameter {k} is not an OS parameter in {config}.")
        return cls(**endkwargs)

@dataclass
class Linbo:
    Cache: str
    Group: str
    AutoFormat: bool = False
    AutoInitCache: bool = False
    AutoPartition: bool = False
    GuiDisabled: bool = False
    KernelOptions: str = ''
    Locale: str = 'de-de'
    RootTimeout: int = 600
    DownloadType: str = 'torrent'
    UseMinimalLayout: bool = False

    @classmethod
    def from_dict(cls, kwargs):
        endkwargs = {}
        config = kwargs['config']
        del kwargs['config']
        for k, v in kwargs.items():
            for p in inspect.signature(cls).parameters:
                if k.lower() == p.lower():
                    endkwargs[p] = v
                    break
            else:
                logging.warning(f"Parameter {k} is not an Linbo parameter in {config}.")
        return cls(**endkwargs)

@dataclass
class LinboConfig:
    LINBO: Linbo
    Partitions: list
    path: str
    OS: list