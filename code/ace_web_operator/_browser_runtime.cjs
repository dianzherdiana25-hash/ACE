/* Runtime Chromium lokal. Selector dan pencatatan hasil tetap tertutup. */
"use strict";

const { createHash } = require("node:crypto");
const fs = require("node:fs");
let chromium;
try { ({ chromium } = require("playwright")); }
catch (_) { process.exit(78); }

function proof(value) {
    const normalized = value.replace(/\s+/gu, " ").trim();
    return { text_sha256: createHash("sha256").update(normalized).digest("hex"), chars: [...normalized].length };
}

async function main() {
    const payload = fs.readFileSync(0);
    if (payload.length > 120000) throw Error("plan_size");
    const plan = JSON.parse(payload);
    if (plan.schema !== "ace.web.browser-runtime.v1" ||
        !/^http:\/\/127\.0\.0\.1:[1-9][0-9]{3,4}$/.test(plan.origin) ||
        Number(new URL(plan.origin).port) < 1024 || !Array.isArray(plan.steps) || plan.steps.length > 40 ||
        !Number.isInteger(plan.request_limit) || plan.request_limit < 1 || plan.request_limit > 140 ||
        !Number.isInteger(plan.timeout_ms) || plan.timeout_ms < 100 || plan.timeout_ms > 3500) throw Error("plan_invalid");
    const paths = new Set(plan.paths);
    if (paths.size > 70 || [...paths].some(p => typeof p !== "string" || !/^\/(?:[a-zA-Z0-9_-][a-zA-Z0-9_.-]{0,79}(?:\/[a-zA-Z0-9_-][a-zA-Z0-9_.-]{0,79})*\/?)?$/.test(p)))
        throw Error("paths_invalid");
    const browser = await chromium.launch({
        executablePath: process.argv[2], headless: true,
        args: ["--disable-background-networking","--disable-sync","--no-first-run",
               "--force-webrtc-ip-handling-policy=disable_non_proxied_udp"],
    });
    try {
        const context = await browser.newContext({serviceWorkers:"block", acceptDownloads:false, deviceScaleFactor:1,
                                                     viewport:{width:1024,height:768}});
        let requests = 0, blocked = 0;
        await context.route("**/*", async route => {
            const request = route.request(), target = new URL(request.url());
            if (request.method() !== "GET" || target.origin !== plan.origin || target.search ||
                !paths.has(target.pathname) || requests >= plan.request_limit) {
                blocked++;
                await route.abort("blockedbyclient");
                return;
            }
            requests++;
            try {
                const response = await route.fetch({maxRedirects:0, timeout:plan.timeout_ms});
                if (response.status() >= 300 && response.status() < 400) {
                    blocked++;
                    await route.abort("blockedbyclient");
                    return;
                }
                await route.fulfill({response});
            } catch (_) {
                await route.abort("failed").catch(()=>{});
            }
        });
        if (typeof context.routeWebSocket === "function") {
            await context.routeWebSocket("**/*", async route => { blocked++; await route.close(); });
        }
        await context.addInitScript(() => {
            for (const name of ["RTCPeerConnection","webkitRTCPeerConnection","WebTransport"]) {
                Object.defineProperty(globalThis,name,{value:undefined,writable:false,configurable:false});
            }
        });
        const page = await context.newPage();
        context.on("page", sibling => { if (sibling !== page) { blocked++; sibling.close().catch(()=>{}); } });
        page.setDefaultTimeout(plan.timeout_ms);
        page.setDefaultNavigationTimeout(plan.timeout_ms);
        const timing = { timeout: plan.timeout_ms };
        const steps = [];
        let reason = null;
        for (const step of plan.steps) {
            let evidence = null;
            try {
                const needsPath = ["navigate","expect_url"].includes(step.op);
                if (needsPath && !paths.has(step.path)) throw Error("path_invalid");
                let control;
                if (["click","fill","select","check","expect_text","read_text","screenshot","expect_value","wait_text","capture_dom","scroll_collect"].includes(step.op)) {
                    if (typeof step.test_id !== "string" || !/^[a-z][a-z0-9_]{0,63}$/.test(step.test_id))
                        throw Error("selector_invalid");
                    control = page.getByTestId(step.test_id);
                }
                switch (step.op) {
                case "navigate": {
                    const result = await page.goto(plan.origin+step.path,{waitUntil:"domcontentloaded",...timing});
                    if (result === null || !result.ok()) throw Error("navigation_response");
                    evidence = { response_status: result.status() };
                    break;
                }
                case "expect_title": {
                    const title = await page.title();
                    evidence = proof(title);
                    if (title !== step.expected) throw Error("assertion_failed");
                    break;
                }
                case "expect_url":
                    if (page.url() !== plan.origin+step.path) throw Error("assertion_failed");
                    evidence = { path: step.path };
                    break;
                case "click": await control.click(timing); break;
                case "fill": await control.fill(step.value,timing); break;
                case "select": await control.selectOption(step.value,timing); break;
                case "check": await control.setChecked(step.state,timing); break;
                case "expect_value": {
                    const typed = await control.inputValue(timing);
                    if (typed !== step.expected) throw Error("assertion_failed");
                    evidence = proof(typed);
                    break;
                }
                case "expect_text":
                case "read_text": {
                    const value = await control.innerText(timing);
                    if (value.length > 12000) throw Error("read_limit");
                    evidence = proof(value);
                    if (step.op === "expect_text" && evidence.text_sha256 !== proof(step.expected).text_sha256)
                        throw Error("assertion_failed");
                    break;
                }
                case "wait_text": {
                    const expected = step.expected.replace(/\s+/gu," ").trim();
                    const tokens = expected.split(" ").map(token => token.replace(/[.*+?^${}()|[\]\\]/g,"\\$&"));
                    await control.filter({hasText:new RegExp("^\\s*"+tokens.join("\\s+")+"\\s*$","u")})
                        .waitFor({state:"visible",...timing});
                    evidence=proof(await control.innerText(timing));
                    if(evidence.text_sha256!==proof(expected).text_sha256)throw Error("assertion_failed");
                    break;
                }
                case "capture_dom": {
                    const result = await control.evaluate(element=>element.outerHTML,undefined,timing);
                    const at = Buffer.from(result,"utf8");
                    if (at.length > 160000) throw Error("dom_limit");
                    evidence={html_base64:at.toString("base64"),bytes:at.length,
                              sha256:createHash("sha256").update(at).digest("hex")};
                    break;
                }
                case "scroll_collect": {
                    const validId = value => typeof value === "string" && /^[a-z][a-z0-9_]{0,63}$/.test(value);
                    if (!validId(step.end_test_id) || (step.next_test_id !== null && !validId(step.next_test_id))
                        || !Number.isInteger(step.max_turns) || step.max_turns < 1 || step.max_turns > 12) throw Error("scroll_contract");
                    const seen = new Set(), counts = [];
                    const end = page.getByTestId(step.end_test_id);
                    const next = step.next_test_id === null ? null : page.getByTestId(step.next_test_id);
                    let terminal = false, stalled = false;
                    for (let turn=0; turn<=step.max_turns; turn++) {
                        const ids=await control.evaluate(element=>Array.from(element.querySelectorAll("[data-item-id]"),
                                                                           child=>child.getAttribute("data-item-id")),
                                                         undefined,timing);
                        if (ids.length > 400 || ids.some(value=>!validId(value))) throw Error("scroll_data");
                        for (const value of ids) seen.add(createHash("sha256").update(value).digest("hex"));
                        counts.push({turn,visible:ids.length,unique:seen.size});
                        if (await end.isVisible()) { terminal=true; break; }
                        if (turn===step.max_turns) break;
                        if (next) await next.click(timing);
                        else await control.evaluate(element=>{element.scrollTop += Math.max(element.clientHeight,120);},undefined,timing);
                        try {
                            await page.waitForFunction(({target,finish,prior}) => {
                                const final = document.querySelector(`[data-testid="${finish}"]`);
                                if (final && final.getClientRects().length && getComputedStyle(final).visibility !== "hidden")
                                    return true;
                                const container = document.querySelector(`[data-testid="${target}"]`);
                                if (!container) return false;
                                const current=Array.from(container.querySelectorAll("[data-item-id]"),
                                                         node=>node.getAttribute("data-item-id"));
                                return current.length!==prior.length || current.some((value,index)=>value!==prior[index]);
                            },{target:step.test_id,finish:step.end_test_id,prior:ids},timing);
                        } catch (error) {
                            if (error.name!=="TimeoutError")throw error;
                            stalled=true;
                            break;
                        }
                    }
                    evidence={terminal,stalled,counts,member_sha256:[...seen].sort()};
                    break;
                }
                case "screenshot": {
                    const geometry = await control.boundingBox(timing);
                    if (!geometry || geometry.width < 1 || geometry.height < 1 ||
                        geometry.width > 1100 || geometry.height > 800) throw Error("capture_geometry");
                    const png = await control.screenshot({type:"png",animations:"disabled",scale:"css",...timing});
                    if (png.length > 600000) throw Error("capture_size");
                    evidence = {png_base64:png.toString("base64"),bytes:png.length,
                                sha256:createHash("sha256").update(png).digest("hex")};
                    break;
                }
                default: throw Error("operation_invalid");
                }
                if (blocked) throw Error("request_rejected");
                steps.push({id:step.id,op:step.op,status:"ok",evidence});
            } catch (error) {
                if (blocked) reason = "request_rejected";
                else if (error.name === "TimeoutError") reason = "operation_timeout";
                else if (["navigation_response","assertion_failed","read_limit"].includes(error.message)) reason = error.message;
                else reason = "operation_failed";
                steps.push({id:step.id,op:step.op,status:"failed",evidence});
                break;
            }
        }
        if (blocked && !reason) reason="request_rejected";
        await context.close();
        process.stdout.write(JSON.stringify({status:reason?"failed":"completed",reason,requests,blocked,steps})+"\n");
    } finally {
        await browser.close();
    }
}

main().catch(() => { process.exitCode = 1; });
