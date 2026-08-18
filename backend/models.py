"""Pydantic schemas for all API request bodies."""
from pydantic import BaseModel


class Suffix(BaseModel):
    suffix: str
    dpt: str


class PointTypeIn(BaseModel):
    category_id: int
    name: str
    suffixes: list[Suffix]
    block_size: int = 5
    channel_type: str = ""      # must match an Actor Type's channel_type to be assignable to a circuit
    channels_needed: int = 1    # how many physical actuator channels one instance of this point needs


class CentralTemplateIn(BaseModel):
    category_id: int
    name: str
    scope: str  # 'building' | 'floor' | 'room_multi'
    suffixes: list[Suffix]
    order_idx: int = 0
    skip_outdoor_floors: bool = False
    block_size: int | None = None      # only meaningful for scope='room_multi' - pads with "res"
    trigger_count: int | None = None   # only meaningful for scope='room_multi' - min points to trigger (default 2)


class ProjectIn(BaseModel):
    name: str
    location: str = ""
    customer: str = ""
    status: str = ""
    comment: str = ""
    order_number: str = ""


class FloorIn(BaseModel):
    name: str
    is_outdoor: bool = False


class RoomIn(BaseModel):
    name: str


class CategoryRenameIn(BaseModel):
    name: str


class RoomPointIn(BaseModel):
    point_type_id: int
    label: str = ""
    quantity: int = 1  # convenience: add N identical points at once (auto-numbered if no label)
    has_bwm: bool = False  # adds one extra "BWM" (motion sensor) address to this point


class RoomPointEditIn(BaseModel):
    point_type_id: int
    label: str = ""
    has_bwm: bool = False


class SpecialItemIn(BaseModel):
    category_id: int
    location: str  # 'central' or floor id as string
    name: str
    suffixes: list[Suffix]


class ActorTypeIn(BaseModel):
    manufacturer: str = ""
    model: str
    group_name: str = "Aktor"    # "Aktor", "Sensor", "Wetterstation", "Bedienelement", or custom
    description: str = ""
    channel_type: str = ""       # only meaningful for group_name == "Aktor"
    channel_count: int | None = None  # only meaningful for group_name == "Aktor"
    # DIN-rail width in Teilungseinheiten (1 TE = 18mm) - only meaningful for
    # rail-mounted devices; blank if not applicable.
    width_te: int | None = None


class ActorInstanceIn(BaseModel):
    actor_type_id: int
    floor_id: int | None = None
    location_label: str = ""
    physical_address: str = ""


class ChannelAssignIn(BaseModel):
    room_point_id: int
    channel_seq: int = 0
    actor_instance_id: int
    channel_letter: str


class RoomDeviceIn(BaseModel):
    device_type_id: int
    quantity: int = 1
    note: str = ""


class VerteilerIn(BaseModel):
    floor_id: int | None = None
    name: str = ""
    row_count: int = 4


class VerteilerUpdateIn(BaseModel):
    name: str
    row_count: int


class VerteilerItemIn(BaseModel):
    row_idx: int
    item_type: str          # 'rcd' | 'ls' | 'device'
    label: str = ""         # only used for rcd/ls
    width_te: int | None = None   # only used for rcd/ls - server fills a default if omitted
    actor_instance_id: int | None = None   # required for item_type == 'device'


class VerteilerItemMoveIn(BaseModel):
    direction: str   # 'left' | 'right'


class KlaerungIn(BaseModel):
    room_id: int | None = None
    room_point_id: int | None = None
    text: str
    typ: str = "Frage"       # "Frage" | "Aufgabe" | "Notiz"
    status: str = "offen"    # "offen" | "geklärt" | "abgelehnt"
    antwort: str = ""


class CompanyProfileIn(BaseModel):
    name: str = ""
    address: str = ""
    email: str = ""
    website: str = ""
    phone: str = ""
    logo_data_url: str = ""   # data URL, or "" to clear the logo
    show_on_pdf: bool = False
    pflichtenheft_preamble: str = ""
    pflichtenheft_include_vorbemerkungen: bool = True
    pflichtenheft_include_struktur: bool = True
    pflichtenheft_include_geraeteliste: bool = True
    pflichtenheft_include_gruppenadressen: bool = False
    pflichtenheft_include_abgangsliste: bool = False
    pflichtenheft_include_klaerungsliste: bool = False
    backup_enabled: bool = False
    backup_interval_hours: int = 24
    backup_retention_count: int = 14
    backup_local_enabled: bool = False
    backup_local_path: str = ""
    backup_nextcloud_enabled: bool = False
    backup_nextcloud_url: str = ""
    backup_nextcloud_username: str = ""
    backup_nextcloud_password: str = ""
