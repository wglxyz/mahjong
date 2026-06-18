// Catch script-evaluation errors (e.g. "Class extends undefined" from a wrong
// engine load order) WITHOUT a browser. Evaluates the vendored Laya scripts in
// the given order under minimal browser stubs. WebGL/runtime errors are NOT
// caught here (they need a real browser) — only eval-time errors.
//
// Usage: node tools/check-engine-load.cjs laya.core.js laya.webgl_2D.js laya.d3.js laya.webgl_3D.js
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const libs = process.argv.slice(2);
if (!libs.length) { console.error("pass lib filenames (in load order)"); process.exit(2); }

// permissive stub: any property access returns a callable/constructable proxy
const anyProxy = new Proxy(function () {}, {
  get: (t, p) => (p === Symbol.toPrimitive ? () => 0 : (p in t ? t[p] : anyProxy)),
  set: () => true, apply: () => anyProxy, construct: () => ({}),
});
const documentStub = new Proxy({ createElement: () => anyProxy, getElementById: () => anyProxy,
  addEventListener: () => {}, documentElement: anyProxy, body: anyProxy, head: anyProxy }, {
  get: (t, p) => (p in t ? t[p] : anyProxy) });

const sandbox = {};
sandbox.window = sandbox;
sandbox.self = sandbox;
sandbox.globalThis = sandbox;
sandbox.document = documentStub;
sandbox.navigator = { userAgent: "node", language: "en", platform: "node" };
sandbox.location = { href: "http://localhost/", protocol: "http:", host: "localhost" };
sandbox.performance = { now: () => Date.now() };
sandbox.console = console;
sandbox.requestAnimationFrame = () => 0;
sandbox.setTimeout = setTimeout; sandbox.clearTimeout = clearTimeout;
sandbox.WebGLRenderingContext = function () {}; sandbox.WebGL2RenderingContext = function () {};
sandbox.Image = function () {}; sandbox.XMLHttpRequest = function () {};
vm.createContext(sandbox);

const libsDir = path.resolve(__dirname, "..", "public", "libs");
let ok = true;
for (const name of libs) {
  const code = fs.readFileSync(path.join(libsDir, name), "utf8");
  // make the footer's free `Laya` reference resolve to the global we built up
  sandbox.Laya = sandbox.Laya || undefined;
  try {
    vm.runInContext(code + "\n;globalThis.Laya = window.Laya;", sandbox, { filename: name });
    console.log(`OK   ${name}  (Laya keys: ${sandbox.Laya ? Object.keys(sandbox.Laya).length : 0})`);
  } catch (e) {
    ok = false;
    console.error(`FAIL ${name}: ${e.message}`);
    break;
  }
}
process.exit(ok ? 0 : 1);
