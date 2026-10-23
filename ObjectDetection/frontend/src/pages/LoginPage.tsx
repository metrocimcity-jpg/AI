import { FormEvent, useState } from "react";
import { HardHat } from "lucide-react";
import { api, setToken } from "../api/client";

export function LoginPage({ onDone }: { onDone: () => void }) {
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      const body = await api<{ access_token: string }>("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({
          username: form.get("username"),
          password: form.get("password"),
        }),
      });
      setToken(body.access_token);
      onDone();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    }
  }

  return (
    <div className="grid min-h-full place-items-center p-6">
      <form className="card w-full max-w-sm space-y-4 p-6" onSubmit={(event) => void submit(event)}>
        <div className="flex items-center gap-2">
          <HardHat className="text-safety" />
          <h1 className="text-xl font-semibold">SiteGuard</h1>
        </div>
        <p className="text-sm text-[var(--muted)]">Local sign-in. Nothing leaves this machine. Default account is admin / changeme.</p>
        <label className="block text-sm">
          Username
          <input name="username" autoComplete="username" required className="mt-1 w-full rounded-lg bg-transparent px-3 py-2 ring-1 ring-white/15" />
        </label>
        <label className="block text-sm">
          Password
          <input name="password" type="password" autoComplete="current-password" required className="mt-1 w-full rounded-lg bg-transparent px-3 py-2 ring-1 ring-white/15" />
        </label>
        {error ? <p className="text-sm text-red-500">{error}</p> : null}
        <button className="w-full rounded-xl bg-safety py-2 text-black" type="submit">
          Sign in
        </button>
      </form>
    </div>
  );
}
