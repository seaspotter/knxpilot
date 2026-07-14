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


class RoomPointIn(BaseModel):
    point_type_id: int
    label: str = ""
    quantity: int = 1  # convenience: add N identical points at once (auto-numbered if no label)
    has_bwm: bool = False  # adds one extra "BWM" (motion sensor) address to this point


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
