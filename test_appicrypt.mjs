globalThis.window = {
    origin: "https://www.diskwala.com",
    location: {
        origin: "https://www.diskwala.com",
        href: "https://www.diskwala.com/app/6ac9c34d2a52418b24ee459d"
    }
};
globalThis.location = globalThis.window.location;
globalThis.document = {
    location: globalThis.window.location,
    referrer: "https://www.diskwala.com/"
};
globalThis.origin = "https://www.diskwala.com";

import fs from 'fs';
import crypto from 'crypto';
import * as appicrypt from './appicrypt_node.js';

const qt = fs.readFileSync('qt.txt', 'utf-8').trim();

async function main() {
    try {
        await appicrypt.setMagicFile(qt);
        console.log("setMagicFile SUCCESS!");

        const method = "POST";
        const urlPath = "/file/temp_info";
        const data = { id: "6ac9c34d2a52418b24ee459d" };
        const ts = Date.now().toString();

        function Yt(e) {
            if (null === e || void 0 === e) return "";
            if ("object" !== typeof e) return JSON.stringify(e);
            if (Array.isArray(e)) return `[${e.map(Yt).join(",")}]`;
            return `{${Object.keys(e).sort().map(t => `${JSON.stringify(t)}:${Yt(e[t])}`).join(",")}}`;
        }

        const bodyStr = Yt(data);
        const signStr = `${method} ${urlPath} | params= | body=${bodyStr} | ts=${ts}`;
        console.log("signStr:", signStr);

        const hash = crypto.createHash('sha256').update(signStr).digest();
        const cryptogram = await appicrypt.getCryptogram(new Uint8Array(hash));
        console.log("Cryptogram:", cryptogram);
        console.log("ts:", ts);

        const res = await fetch("https://ddudapidd.diskwala.com/api/v1/file/temp_info", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Appicrypt": cryptogram,
                "Appicrypt-ts": ts,
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Origin": "https://www.diskwala.com",
                "Referer": "https://www.diskwala.com/"
            },
            body: JSON.stringify(data)
        });

        console.log("API Status:", res.status);
        const resText = await res.text();
        console.log("API Response:", resText);
    } catch (e) {
        console.error("Error:", e);
    }
}

main();
