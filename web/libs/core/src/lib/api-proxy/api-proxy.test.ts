/**
 * PUT must carry its JSON body.
 *
 * `getDefaultHeaders` used to set `Content-Type: application/json` for POST/PATCH/DELETE
 * only. The body serializer keys off that header, so a PUT went out with **no body** —
 * the server saw an empty payload and, because every field of the compensation policy
 * has a model default, silently created a "USD, 0.00" policy. `setProjectCompensationPolicy`
 * is the repo's only PUT endpoint, which is why nothing else surfaced it.
 */
import { APIProxy } from "./index";

const endpoints = {
  putThing: "PUT:/things/:pk",
  postThing: "POST:/things",
  getThing: "/things/:pk",
};

function setupFetch() {
  const calls: RequestInit[] = [];
  global.fetch = jest.fn(async (_url: any, init: any) => {
    calls.push(init);
    return {
      ok: true,
      status: 200,
      headers: new Headers({ "Content-Type": "application/json" }),
      json: async () => ({}),
      text: async () => "{}",
    } as any;
  }) as any;
  return calls;
}

describe("APIProxy request body", () => {
  let api: APIProxy;
  let calls: RequestInit[];

  beforeEach(() => {
    calls = setupFetch();
    api = new APIProxy({ gateway: "/api", endpoints });
  });

  it("sends a JSON body on PUT", async () => {
    await (api.methods as any).putThing({ pk: 1 }, { body: { currency: "KRW", annotation_unit_price: 100 } });

    const init = calls[0];
    expect(init.method).toBe("PUT");
    expect(new Headers(init.headers).get("Content-Type")).toBe("application/json");
    expect(init.body).toBeDefined();
    expect(JSON.parse(init.body as string)).toMatchObject({ currency: "KRW", annotation_unit_price: 100 });
  });

  it("still sends a JSON body on POST", async () => {
    await (api.methods as any).postThing({}, { body: { a: 1 } });
    expect(JSON.parse(calls[0].body as string)).toMatchObject({ a: 1 });
  });

  it("sends no body on GET", async () => {
    await (api.methods as any).getThing({ pk: 1 });
    expect(calls[0].body).toBeUndefined();
  });
});
