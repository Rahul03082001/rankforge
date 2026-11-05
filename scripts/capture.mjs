import { chromium } from '../frontend/node_modules/playwright/index.mjs';
const browser = await chromium.launch();
const page = await browser.newPage({viewport:{width:1440,height:1000},deviceScaleFactor:1});
await page.goto(process.env.BASE_URL || 'http://localhost:7860');
await page.waitForFunction(()=>document.body.innerText.includes('Search engine ready'));
await page.screenshot({path:'reports/search-desktop.png',fullPage:true});
await page.setViewportSize({width:390,height:844});
await page.screenshot({path:'reports/search-mobile.png',fullPage:true});
await browser.close();
