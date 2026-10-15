from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .config import MAX_DISTANCE_M


class Coordinate(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)

    def pair(self):
        return (self.lon, self.lat)


class MissionRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")
    start: Coordinate
    end: Coordinate | None = None
    bearing: float | None = Field(default=None, ge=0, lt=360)
    distance_m: float | None = Field(default=None, ge=10, le=MAX_DISTANCE_M)
    max_deviation_m: float = Field(default=50, ge=1, le=2000)
    strict: bool = True
    allow_unverified_crossings: bool = True

    @model_validator(mode="after")
    def check_destination(self):
        if self.end is None and (self.bearing is None or self.distance_m is None):
            raise ValueError("Choose a finish point or provide bearing and distance.")
        if self.end is not None and (self.bearing is not None or self.distance_m is not None):
            raise ValueError("Use endpoints or bearing and distance, not both.")
        return self


class DiscoveryRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")
    west: float = Field(ge=-180, le=180)
    south: float = Field(ge=-90, le=90)
    east: float = Field(ge=-180, le=180)
    north: float = Field(ge=-90, le=90)
    min_length_m: float = Field(default=1000, ge=100, le=10000)
    max_length_m: float = Field(default=3000, ge=100, le=10000)
    max_deviation_m: float = Field(default=100, ge=1, le=1000)
    max_results: int = Field(default=5, ge=1, le=10)
    strict: bool = True
    allow_unverified_crossings: bool = True
    terrain: Literal["any", "paved", "trail"] = "any"

    @model_validator(mode="after")
    def check_bounds(self):
        if self.north <= self.south or self.west == self.east:
            raise ValueError("Select a nonempty rectangular search area.")
        if self.max_length_m < self.min_length_m:
            raise ValueError("Maximum length must be at least minimum length.")
        return self
