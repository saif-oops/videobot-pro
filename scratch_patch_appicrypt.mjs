import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

let content = fs.readFileSync('appicrypt.js', 'utf-8');

// Replace c3 with local fs read
const oldC3 = 'async function c3(){t2._wby=new Uint8Array(await (await fetch(e3())).arrayBuffer());t2._mp=import.meta.url;}';
const newC3 = `async function c3(){
    const wasmPath = path.join(__dirname, "appicrypt-web-f-0_1_216-bg.wasm");
    t2._wby = new Uint8Array(fs.readFileSync(wasmPath));
    t2._mp = import.meta.url;
}`;

content = `import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
const __dirname = path.dirname(fileURLToPath(import.meta.url));
` + content.replace(oldC3, newC3);

fs.writeFileSync('appicrypt_node.js', content);
console.log("Wrote appicrypt_node.js!");
