// Copy the browser builds of htmx, Alpine.js, ECharts, sigma.js and graphology (with their licences) from
// node_modules into static/vendor/<package>/<version>/ and record the versions in static/vendor/README.md. Run
// `npm run vendor` after changing their versions in package.json, then update the script tags
// (theme/templates/base.html for htmx and Alpine, templates/nrmps/runs/_layout.html for the chart libraries) and
// commit the vendored files.
import { copyFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const vendorDir = join(here, "..", "..", "static", "vendor");
const files = [
  { pkg: "htmx.org", dir: "htmx", from: "dist/htmx.min.js", to: "htmx.min.js" },
  { pkg: "alpinejs", dir: "alpinejs", from: "dist/cdn.min.js", to: "alpine.min.js" },
  { pkg: "echarts", dir: "echarts", from: "dist/echarts.min.js", to: "echarts.min.js" },
  { pkg: "sigma", dir: "sigma", from: "dist/sigma.min.js", to: "sigma.min.js" },
  { pkg: "graphology", dir: "graphology", from: "dist/graphology.umd.min.js", to: "graphology.umd.min.js" },
];
const licences = ["LICENSE", "LICENSE.md", "LICENSE.txt", "NOTICE"];

const lines = ["# Vendored browser libraries", "", "Copied from npm by `npm run vendor` in theme/static_src.", ""];
for (const { pkg, dir, from, to } of files) {
  const { version } = JSON.parse(readFileSync(join(here, "node_modules", pkg, "package.json"), "utf8"));
  const target = join(vendorDir, dir, version);
  mkdirSync(target, { recursive: true });
  const source = join(here, "node_modules", pkg, from);
  copyFileSync(source, join(target, to));
  // A source map the file points to must come too: Django's manifest storage (collectstatic) resolves the reference.
  const map = readFileSync(source, "utf8").match(/\/\/# sourceMappingURL=(\S+)\s*$/);
  if (map) copyFileSync(join(dirname(source), map[1]), join(target, map[1]));
  const copied = licences.filter((name) => existsSync(join(here, "node_modules", pkg, name)));
  for (const name of copied) copyFileSync(join(here, "node_modules", pkg, name), join(target, name));
  const { license } = JSON.parse(readFileSync(join(here, "node_modules", pkg, "package.json"), "utf8"));
  const notes = copied.length ? `${license}; ${copied.join(", ")}` : license;
  lines.push(`- \`${dir}/${version}/${to}\`: ${pkg} ${version} (${from}; ${notes})`);
  console.log(`${pkg} ${version} -> static/vendor/${dir}/${version}/${to}`);
}
writeFileSync(join(vendorDir, "README.md"), lines.join("\n") + "\n");
