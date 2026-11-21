/* Jalankan produk fixture dalam Chromium lokal, dengan rute di luar origin diblokir. */
const assert = require("node:assert/strict");
const { chromium } = require("playwright");

async function run() {
    const port = Number(process.argv[2]);
    const address = `http://127.0.0.1:${port}`;
    assert.ok(Number.isInteger(port) && port > 0 && port <= 65535);
    const browser = await chromium.launch({
        executablePath: process.argv[3],
        headless: true,
        args: ["--disable-background-networking", "--disable-sync", "--no-first-run"],
    });
    try {
        const context = await browser.newContext({ serviceWorkers: "block" });
        const blocked = [];
        await context.route("**/*", async (route) => {
            const url = new URL(route.request().url());
            if (url.origin !== address) {
                blocked.push(url.origin);
                await route.abort();
                return;
            }
            await route.continue();
        });
        const page = await context.newPage();
        const loaded = await page.goto(address, { waitUntil: "domcontentloaded" });
        assert.equal(loaded.status(), 200);
        await page.getByRole("textbox", { name: "Nama" }).fill("Kotak alat");
        const saved = page.waitForResponse((response) =>
            response.url() === address + "/categories" && response.request().method() === "POST");
        await page.getByRole("button", { name: "Tambah" }).click();
        assert.equal((await saved).status(), 201);
        await page.getByRole("status").getByText("Tercatat").waitFor();
        const observed = await page.request.get(address + "/categories/1");
        assert.equal(observed.status(), 200);
        assert.deepEqual(await observed.json(), { id: 1, name: "Kotak alat" });
        assert.deepEqual(blocked, []);
        process.stdout.write(JSON.stringify({ submitted: 201, fetch: 200, returned: "Kotak alat" }) + "\n");
    } finally {
        await browser.close();
    }
}

run().catch((error) => {
    process.stderr.write(error.message + "\n");
    process.exitCode = 1;
});
