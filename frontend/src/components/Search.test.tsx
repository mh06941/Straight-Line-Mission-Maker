import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import Search from "./Search";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
it("submits Unicode places explicitly and lets users select the provider result", async () => {
  const fetcher = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => [
      { id: "1", label: "京都市, 日本", lat: 35.01, lon: 135.76 },
    ],
  });
  vi.stubGlobal("fetch", fetcher);
  const select = vi.fn();
  render(
    <QueryClientProvider client={new QueryClient()}>
      <Search onPlace={select} />
    </QueryClientProvider>,
  );
  fireEvent.change(screen.getByRole("textbox"), {
    target: { value: "京都市" },
  });
  expect(fetcher).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Search location" }));
  fireEvent.click(await screen.findByRole("button", { name: "京都市, 日本" }));
  await waitFor(() =>
    expect(select).toHaveBeenCalledWith(
      expect.objectContaining({ lat: 35.01 }),
    ),
  );
});
it("accepts coordinates without using a public geocoder", () => {
  const fetcher = vi.fn();
  vi.stubGlobal("fetch", fetcher);
  const select = vi.fn();
  render(
    <QueryClientProvider client={new QueryClient()}>
      <Search onPlace={select} />
    </QueryClientProvider>,
  );
  fireEvent.change(screen.getByRole("textbox"), {
    target: { value: "-85, 179.9" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Search location" }));
  expect(select).toHaveBeenCalledWith(
    expect.objectContaining({ lat: -85, lon: 179.9 }),
  );
  expect(fetcher).not.toHaveBeenCalled();
});
