import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "./client";

function jsonResponse(status: number, body: unknown) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("api client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns parsed JSON on success", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(200, { id: "1", name: "Alice" })));
    const result = await api.get<{ id: string; name: string }>("/users/1");
    expect(result).toEqual({ id: "1", name: "Alice" });
  });

  it("returns undefined for a 204 No Content response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 204 })));
    const result = await api.delete("/users/1");
    expect(result).toBeUndefined();
  });

  it("throws ApiError with the string detail message on a non-2xx response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(404, { detail: "User not found" })));
    await expect(api.get("/users/missing")).rejects.toMatchObject(
      new ApiError(404, "User not found", "User not found"),
    );
  });

  it("throws ApiError using the object detail's message field", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(422, { detail: { code: "invalid", message: "Bad email" } })),
    );
    await expect(api.post("/users", { email: "x" })).rejects.toMatchObject({
      status: 422,
      message: "Bad email",
    });
  });

  it("falls back to statusText when the error response has no JSON body", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("", { status: 500, statusText: "Internal Server Error" })),
    );
    await expect(api.get("/broken")).rejects.toMatchObject({ status: 500, message: "Internal Server Error" });
  });
});
