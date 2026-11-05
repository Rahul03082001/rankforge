import {test,expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
test('real search, keyboard modes, source navigation, and axe',async({page})=>{
  await page.goto('/');
  await expect(page.getByText('Search engine ready')).toBeVisible();
  await expect(new AxeBuilder({page}).analyze().then(r=>r.violations)).resolves.toEqual([]);
  await page.getByLabel('What would you like to explore?').focus();
  await page.keyboard.type('interest rates');
  await page.keyboard.press('Enter');
  await expect(page.locator('.result')).not.toHaveCount(0);
  await page.getByRole('radio',{name:/Keyword/}).focus();
  await page.keyboard.press('Space');
  await expect(page.getByRole('radio',{name:/Keyword/})).toBeChecked();
  await expect(page.locator('.results .score').first()).toContainText('BM25');
  const first=page.locator('.result h3 a').first();
  const text=await first.innerText();
  await first.focus();await page.keyboard.press('Enter');
  await expect(page.locator('h1')).toHaveText(text);
  await expect(page.locator('h1')).toBeFocused();
  await page.getByRole('button',{name:'Back to results'}).click();
  await expect(page.locator('.result h3 a').first()).toBeFocused();
  const violations=(await new AxeBuilder({page}).analyze()).violations;
  expect(violations).toEqual([]);
});
test('stale responses cannot overwrite newer results',async({page})=>{
  await page.route('**/api/search?**',async route=>{
    const q=new URL(route.request().url()).searchParams.get('q')!;
    if(q==='older')await new Promise(r=>setTimeout(r,800));
    await route.fulfill({json:{query:q,mode:'hybrid',server_ms:1,results:[{id:q,title:q,excerpt:q,mode:'hybrid',score:1}]}}).catch(()=>{});
  });
  await page.goto('/');await expect(page.getByText('Search engine ready')).toBeVisible();
  await page.getByLabel('What would you like to explore?').fill('older');
  await page.getByRole('button',{name:'Search',exact:true}).click();
  await page.getByLabel('What would you like to explore?').fill('newer');
  await page.getByRole('button',{name:'Search',exact:true}).click();
  await expect(page.locator('.result h3')).toHaveText('newer');
  await page.waitForTimeout(1000);
  await expect(page.locator('.result h3')).toHaveText('newer');
});
test('errors are readable; comparison and evaluation open',async({page})=>{
  await page.goto('/');await expect(page.getByText('Search engine ready')).toBeVisible();
  await page.route('**/api/search?**',r=>r.fulfill({status:503,json:{detail:'Search temporarily unavailable'}}));
  await page.getByLabel('What would you like to explore?').fill('savings');
  await page.getByRole('button',{name:'Search',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('Search temporarily unavailable');
  await page.unroute('**/api/search?**');
  await page.getByRole('button',{name:'Compare modes'}).click();
  await page.getByRole('button',{name:'Search',exact:true}).click();
  await expect(page.locator('.comparison-grid>section')).toHaveCount(4);
  await page.getByRole('button',{name:'Benchmark result',exact:true}).click();
  await expect(page.locator('table').first()).toBeVisible();
  expect((await new AxeBuilder({page}).analyze()).violations).toEqual([]);
});
test('mobile layout does not overflow',async({page})=>{
  await page.setViewportSize({width:390,height:844});await page.goto('/');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  expect((await new AxeBuilder({page}).analyze()).violations).toEqual([]);
});
test('missing artifacts render an unavailable state without crashing',async({page})=>{
  await page.route('**/api/status',r=>r.fulfill({json:{ready:false,available_modes:[],documents:0,metadata:null,bundle_version:null,message:'Search artifacts are missing or incompatible.'}}));
  await page.goto('/');
  await expect(page.getByRole('alert')).toContainText('Search artifacts are missing');
  await expect(page.getByRole('button',{name:'Search',exact:true})).toBeDisabled();
  await expect(page.getByRole('radio',{name:/Learned ranking/})).toBeDisabled();
  expect((await new AxeBuilder({page}).analyze()).violations).toEqual([]);
});
