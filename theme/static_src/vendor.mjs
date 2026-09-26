// Copy the browser builds of htmx and Alpine.js from node_modules into static/vendor/<package>/<version>/ and record
// the versions in static/vendor/README.md. Run `npm run vendor` after changing their versions in package.json, then
// update the script tags in theme/templates/base.html and commit the vendored files.
import { copyFileSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const vendorDir = join(here, "..", "..", "static", "vendor");
const files = [
  { pkg: "htmx.org", dir: "htmx", from: "dist/htmx.min.js", to: "htmx.min.js" },
  { pkg: "alpinejs", dir: "alpinejs", from: "dist/cdn.min.js", to: "alpine.min.js" },
];

const lines = ["# Vendored browser libraries", "", "Copied from npm by `npm run vendor` in theme/static_src.", ""];
for (const { pkg, dir, from, to } of files) {
  const { version } = JSON.parse(readFileSync(join(here, "node_modules", pkg, "package.json"), "utf8"));
  const target = join(vendorDir, dir, version);
  mkdirSync(target, { recursive: true });
  copyFileSync(join(here, "node_modules", pkg, from), join(target, to));
  lines.push(`- \`${dir}/${version}/${to}\`: ${pkg} ${version} (${from})`);
  console.log(`${pkg} ${version} -> static/vendor/${dir}/${version}/${to}`);
}
writeFileSync(join(vendorDir, "README.md"), lines.join("\n") + "\n");
