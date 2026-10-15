import { afterEach, expect, it, vi } from "vitest";
import { api } from "./api";

afterEach(() => vi.unstubAllGlobals());

it("identifies an older API without silently removing the crossing option", async () => {
  const fetcher = vi.fn().mockResolvedValue({
    ok: false,
    status: 422,
    json: async () => ({
      detail: [
        {
          type: "extra_forbidden",
          loc: ["body", "allow_unverified_crossings"],
          msg: "Extra inputs are not permitted",
          input: true,
        },
      ],
    }),
  });
  vi.stubGlobal("fetch", fetcher);
  await expect(
    api("/missions/preview", { allow_unverified_crossings: true }),
  ).rejects.toThrow(
    "The API server is older than this frontend. Stop it and restart it from the updated project's backend folder.",
  );
  expect(fetcher).toHaveBeenCalledTimes(1);
  expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual({
    allow_unverified_crossings: true,
  });
});

it("preserves ordinary request validation errors", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      json: async () => ({
        detail: [
          {
            type: "less_than_equal",
            loc: ["body", "start", "lat"],
            msg: "Input should be less than or equal to 90",
          },
        ],
      }),
    }),
  );
  await expect(api("/missions/preview", {})).rejects.toThrow(
    "Input should be less than or equal to 90",
  );
});
