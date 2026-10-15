export async function api<T>(
  path: string,
  body?: unknown,
  signal?: AbortSignal,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      method: body === undefined ? "GET" : "POST",
      headers:
        body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError")
      throw error;
    throw new Error(
      "Cannot reach StraightLine. Check that the API is running and try again.",
    );
  }
  const data = await response.json();
  if (!response.ok) {
    const detail = data.detail;
    if (
      response.status === 422 &&
      Array.isArray(detail) &&
      detail.some(
        (issue: { type?: string; loc?: (string | number)[] }) =>
          issue.type === "extra_forbidden" &&
          issue.loc?.join(".") === "body.allow_unverified_crossings",
      )
    ) {
      throw new Error(
        "The API server is older than this frontend. Stop it and restart it from the updated project's backend folder.",
      );
    }
    throw new Error(
      Array.isArray(detail)
        ? detail.map((d: { msg: string }) => d.msg).join(" ")
        : detail || "The request could not complete.",
    );
  }
  return data as T;
}
