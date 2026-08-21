import { existsSync, readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";

let failures = 0;

function report(level, name, detail) {
  console.log(`${level.padEnd(4)} ${name}: ${detail}`);
  if (level === "FAIL") failures += 1;
}

function command(command, args) {
  return spawnSync(command, args, { encoding: "utf8" });
}

function localEnvironment() {
  if (!existsSync(".env")) return {};
  const values = {};
  for (const line of readFileSync(".env", "utf8").split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#") || !trimmed.includes("=")) continue;
    const index = trimmed.indexOf("=");
    const key = trimmed.slice(0, index).trim();
    const value = trimmed.slice(index + 1).trim().replace(/^['"]|['"]$/g, "");
    values[key] = value;
  }
  return values;
}

const nodeMajor = Number(process.versions.node.split(".")[0]);
report(nodeMajor >= 20 ? "PASS" : "FAIL", "Node.js", `${process.versions.node} (requires >=20)`);

const python = existsSync(".venv/bin/python") ? ".venv/bin/python" : "python3";
const curlVersion = command("curl", ["--version"]);
report(
  curlVersion.status === 0 ? "PASS" : "FAIL",
  "curl",
  curlVersion.status === 0 ? "available for startup readiness probes" : "required by start.sh",
);
const pythonVersion = command(python, ["-c", "import sys; print('.'.join(map(str, sys.version_info[:3])))"]);
if (pythonVersion.status === 0) {
  const [major, minor] = pythonVersion.stdout.trim().split(".").map(Number);
  report(major > 3 || (major === 3 && minor >= 11) ? "PASS" : "FAIL", "Python", `${pythonVersion.stdout.trim()} (requires >=3.11)`);
} else {
  report("FAIL", "Python", "python3 was not found");
}

const fts = command(python, ["-c", "import sqlite3; c=sqlite3.connect(':memory:'); c.execute('create virtual table t using fts5(x)'); print(sqlite3.sqlite_version)"]);
report(fts.status === 0 ? "PASS" : "FAIL", "SQLite FTS5", fts.status === 0 ? `available (SQLite ${fts.stdout.trim()})` : "unavailable in Python sqlite3");

for (const directory of ["apps/api", "apps/web", "data", "reports"]) {
  report(existsSync(directory) ? "PASS" : "FAIL", "Directory", directory);
}
for (const file of ["infra/searxng/compose.yml", "infra/searxng/settings.yml"]) {
  report(existsSync(file) ? "PASS" : "FAIL", "MAFER infrastructure", file);
}

report(existsSync(".env") ? "PASS" : "WARN", "Environment", existsSync(".env") ? ".env present" : ".env absent; defaults work, copy .env.example for configuration");
const apiDependencies = command(python, [
  "-c",
  "import fastapi,httpx,sqlalchemy,telethon,uvicorn; print('FastAPI, SQLAlchemy, httpx, Telethon, Uvicorn')",
]);
report(
  apiDependencies.status === 0 ? "PASS" : "FAIL",
  "API dependencies",
  apiDependencies.status === 0
    ? `${apiDependencies.stdout.trim()} installed`
    : "missing package; run npm run install:all",
);
report(existsSync("apps/web/node_modules/vite") ? "PASS" : "FAIL", "Web dependencies", existsSync("apps/web/node_modules/vite") ? "installed" : "run npm run install:all");

if (existsSync(".venv/bin/python")) {
  const database = command(".venv/bin/python", ["-c", "from mirsad_api.database import init_database, engine; init_database(engine); c=engine.connect(); print(c.exec_driver_sql('pragma integrity_check').scalar_one()); c.close()"]);
  report(database.status === 0 && database.stdout.trim() === "ok" ? "PASS" : "FAIL", "Database", database.status === 0 ? database.stdout.trim() : "initialization failed");

  const connectors = command(".venv/bin/python", [
    "-c",
    "from mirsad_api.config import Settings; from mirsad_api.services.registry import build_connector_registry; r=build_connector_registry(Settings()); print(', '.join(f'{k}={v.configuration_state()}' for k,v in r.items()))",
  ]);
  report(
    connectors.status === 0 ? "PASS" : "FAIL",
    "Connector metadata",
    connectors.status === 0
      ? connectors.stdout.trim()
      : "connector registry could not be constructed",
  );
}

const environment = { ...localEnvironment(), ...process.env };
const searxngEnabled = ["1", "true", "yes", "on"].includes(
  String(environment.SEARXNG_ENABLED ?? "false").toLowerCase(),
);
if (!searxngEnabled) {
  report("WARN", "SearXNG", "disabled; X, Threads, and Reddit web-index discovery unavailable");
} else {
  const searxngUrl = String(environment.SEARXNG_URL ?? "http://127.0.0.1:8080").replace(/\/$/, "");
  const probe = command("curl", [
    "--silent",
    "--show-error",
    "--fail",
    "--max-time",
    "5",
    `${searxngUrl}/search?q=MIRSAD&format=json`,
  ]);
  report(
    probe.status === 0 ? "PASS" : "WARN",
    "SearXNG JSON API",
    probe.status === 0
      ? "configured backend endpoint accepts JSON search"
      : "enabled but unavailable; start infra/searxng/compose.yml and verify JSON format",
  );
}

console.log(failures ? `\n${failures} required check(s) failed.` : "\nPreflight completed without failures.");
process.exitCode = failures ? 1 : 0;
