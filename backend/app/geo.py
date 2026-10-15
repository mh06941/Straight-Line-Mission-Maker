"""WGS84 geodesics and local metric operations, including polar/date-line areas."""

import math

from pyproj import CRS, Geod, Transformer
from shapely import transform
from shapely.geometry import LineString, Point, mapping

from .config import MAX_DISTANCE_M, SAMPLE_STEP_M
from .models import Coordinate, MissionRequest

GEOD = Geod(ellps="WGS84")


def geodesic_length(coords):
    return sum(GEOD.inv(*a, *b)[2] for a, b in zip(coords, coords[1:]))


def normalize_lon(lon):
    return (lon + 180) % 360 - 180


def densify(coords, step=SAMPLE_STEP_M):
    result = [coords[0]]
    for a, b in zip(coords, coords[1:]):
        distance = GEOD.inv(*a, *b)[2]
        count = max(0, math.ceil(distance / step) - 1)
        if count:
            result.extend(GEOD.npts(*a, *b, count))
        result.append(b)
    return result


class MissionGeometry:
    def __init__(self, request: MissionRequest):
        self.start = request.start
        if request.end:
            self.end = request.end
        else:
            lon, lat, _ = GEOD.fwd(*self.start.pair(), request.bearing, request.distance_m)
            self.end = Coordinate(lat=lat, lon=normalize_lon(lon))
        self.bearing, back, self.distance = GEOD.inv(*self.start.pair(), *self.end.pair())
        self.bearing %= 360
        self.arrival_bearing = (back + 180) % 360
        if self.distance < 10 - 1e-6 or self.distance > MAX_DISTANCE_M + 1e-6:
            raise ValueError(f"Mission length must be between 10 m and {MAX_DISTANCE_M / 1000:g} km.")
        mid = GEOD.fwd(*self.start.pair(), self.bearing, self.distance / 2)
        self.center = (mid[0], mid[1])
        # A route-centered azimuthal equidistant CRS avoids UTM seams and works at the poles.
        crs = CRS.from_proj4(f"+proj=aeqd +lat_0={mid[1]} +lon_0={mid[0]} +datum=WGS84 +units=m")
        self.forward = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
        self.inverse = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
        self.ideal_coords = densify([self.start.pair(), self.end.pair()], 25)
        self.line = LineString([self.forward.transform(*p) for p in self.ideal_coords])

    def project(self, coords):
        return LineString([self.forward.transform(*p) for p in coords])

    def unproject(self, geom):
        return mapping(transform(geom, self.inverse.transform, interleaved=False))

    def display_coords(self, coords):
        # GeoJSON longitudes are unwrapped around the mission to avoid a 360° map segment.
        result = []
        previous = self.start.lon
        for lon, lat in coords:
            lon += 360 * round((previous - lon) / 360)
            result.append([lon, lat])
            previous = lon
        return result

    def deviation(self, coord):
        return Point(self.forward.transform(*coord)).distance(self.line)

    def corridor(self, width):
        geom = self.unproject(self.line.buffer(width, quad_segs=12))
        geom["coordinates"] = [self.display_coords(ring) for ring in geom["coordinates"]]
        return geom

    def bounds(self, padding):
        """One or two Overpass boxes; split at the date line. Polar queries remain bounded by area."""
        buffer = self.line.buffer(padding, quad_segs=12)
        ring = list(buffer.exterior.coords)
        geographic = [self.inverse.transform(*p) for p in ring]
        longitudes = [self.center[0] + normalize_lon(p[0] - self.center[0]) for p in geographic]
        south, north = min(p[1] for p in geographic), max(p[1] for p in geographic)
        if buffer.covers(Point(self.forward.transform(0, 90))):
            return [(south, -180, 90, 180)]
        if buffer.covers(Point(self.forward.transform(0, -90))):
            return [(-90, -180, north, 180)]
        west, east = min(longitudes), max(longitudes)
        if east > 180:
            return [(south, west, north, 180), (south, -180, north, east - 360)]
        if west < -180:
            return [(south, west + 360, north, 180), (south, -180, north, east)]
        return [(south, west, north, east)]

    def preview(self, width):
        return {
            "start": self.start.model_dump(),
            "end": self.end.model_dump(),
            "distance_m": self.distance,
            "initial_bearing": self.bearing,
            "arrival_bearing": self.arrival_bearing,
            "ideal": {"type": "LineString", "coordinates": self.display_coords(self.ideal_coords)},
            "corridor": self.corridor(width),
            "max_deviation_m": width,
        }


def bbox_area(boxes):
    # Integrate ellipsoid surface between parallels. Geodesic-corner polygons
    # underestimate large boxes and collapse for full-longitude polar queries.
    eccentricity_sq = GEOD.es
    eccentricity = math.sqrt(eccentricity_sq)

    def integral(latitude):
        u = math.sin(math.radians(latitude))
        return (u / (1 - eccentricity_sq * u * u) + math.atanh(eccentricity * u) / eccentricity) / 2

    area = 0.0
    for s, w, n, e in boxes:
        area += GEOD.a**2 * (1 - eccentricity_sq) * math.radians(e - w) * (integral(n) - integral(s)) / 1e6
    return area
