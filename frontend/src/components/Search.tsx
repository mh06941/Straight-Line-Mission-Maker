import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { LoaderCircle, MapPin, Search as SearchIcon, X } from "lucide-react";
import { api } from "../lib/api";
import { parseCoordinate } from "../lib/mission";
import type { Place } from "../types";

export default function Search({ onPlace }: { onPlace: (p: Place) => void }) {
  const [input, setInput] = useState("");
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const result = useQuery({
    queryKey: ["geocode", query],
    queryFn: ({ signal }) =>
      api<Place[]>(
        `/geocode?q=${encodeURIComponent(query)}`,
        undefined,
        signal,
      ),
    enabled: query.length >= 2,
    staleTime: 86400000,
  });
  const choose = (place: Place) => {
    onPlace(place);
    setInput(place.label.split(",").slice(0, 2).join(","));
    setOpen(false);
  };
  return (
    <div className="location-search">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          const coord = parseCoordinate(input);
          if (coord) choose({ ...coord, id: "coordinates", label: input });
          else {
            if (query === input.trim() && result.isError) void result.refetch();
            setQuery(input.trim());
            setOpen(true);
          }
        }}
      >
        <SearchIcon size={18} />
        <input
          aria-label="Search worldwide or enter latitude, longitude"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Search places or coordinates"
          minLength={2}
          maxLength={200}
        />
        <button
          className="search-submit"
          type="submit"
          aria-label="Search location"
        >
          {result.isFetching ? (
            <LoaderCircle size={16} className="spin" />
          ) : (
            <span>↵</span>
          )}
        </button>
      </form>
      {open && query.length >= 2 && (
        <div className="search-results">
          <div className="popover-heading">
            Locations
            <button
              className="icon-button"
              onClick={() => setOpen(false)}
              aria-label="Close search results"
            >
              <X size={15} />
            </button>
          </div>
          {result.isFetching && <p>Searching the world…</p>}
          {result.error && (
            <p role="alert">
              {result.error.message} You can also enter latitude, longitude.
            </p>
          )}
          {!result.isFetching && result.data?.length === 0 && (
            <p>No locations found. Try another name or coordinates.</p>
          )}
          {result.data?.map((p) => (
            <button
              className="search-result"
              key={p.id}
              onClick={() => choose(p)}
            >
              <MapPin size={17} />
              <span>{p.label}</span>
            </button>
          ))}
          <small>Search © OpenStreetMap contributors · Nominatim</small>
        </div>
      )}
    </div>
  );
}
