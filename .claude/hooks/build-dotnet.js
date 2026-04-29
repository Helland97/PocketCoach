#!/usr/bin/env node
const { execSync } = require("child_process");
const fs = require("fs");

let raw = "";
try {
  raw = fs.readFileSync(0, "utf8");
} catch {
  process.exit(0);
}

let input = {};
try {
  input = JSON.parse(raw);
} catch {
  // Stop hook payloads should always be JSON, but if not, do nothing.
  process.exit(0);
}

if (input?.stop_hook_active) process.exit(0);

let status = "";
try {
  status = execSync("git status --porcelain Backend/", { encoding: "utf8" });
} catch {
  process.exit(0);
}

const hasCsChange = status
  .split(/\r?\n/)
  .some((line) => /\.cs$/i.test(line));
if (!hasCsChange) process.exit(0);

try {
  execSync("dotnet build Backend/ --nologo -v quiet", { stdio: "inherit" });
} catch {
  console.error(
    `\n.NET build failed after Backend/ changes. Fix before continuing.`
  );
  process.exit(2);
}
