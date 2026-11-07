import { readFile, writeFile } from "node:fs/promises";
import { ASSET_NAMES } from "../src/scene.js";

const dist = new URL("../dist/", import.meta.url);
const read = (path, encoding) => readFile(new URL(path, dist), encoding);
const mimeTypes = { png: "image/png", webp: "image/webp", svg: "image/svg+xml" };

let html = await read("index.html", "utf8");
const script = html.match(/<script type="module"[^>]* src="(\.\/assets\/[^"]+\.js)"><\/script>/);
const style = html.match(/<link rel="stylesheet"[^>]* href="(\.\/assets\/[^"]+\.css)">/);
if (!script || !style) throw new Error("找不到构建后的游戏脚本或样式。");

const [js, css, license, modelEntries] = await Promise.all([
  read(script[1], "utf8"),
  read(style[1], "utf8"),
  read("../node_modules/three/LICENSE", "utf8"),
  Promise.all(ASSET_NAMES.map(async (name) => [name, await read(`models/${name}.glb`, "base64")])),
]);

const images = [...html.matchAll(/(?:src|href)="(\.\/[^"]+\.(png|webp|svg))"/g)];
for (const [, path, extension] of images) {
  const data = await read(path, "base64");
  html = html.replaceAll(`"${path}"`, `"data:${mimeTypes[extension]};base64,${data}"`);
}

const models = `<script type="application/json" id="offline-models">${JSON.stringify(Object.fromEntries(modelEntries))}</script>`;
const game = `<script type="module">${js.replace(/<\/script/gi, "<\\/script")}</script>`;
html = html.replace(script[0], "");
html = html.replace(style[0], () => `<style>${css}</style>`);
html = html.replace("</body>", () => `${models}\n${game}\n<!-- Three.js\n${license}-->\n</body>`);

const output = new URL("肥鱼跑酷.html", dist);
await writeFile(output, html);
console.log("离线版已生成到 dist/肥鱼跑酷.html");
