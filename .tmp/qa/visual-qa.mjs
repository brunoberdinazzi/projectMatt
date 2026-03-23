import { chromium, devices } from 'playwright';

const baseUrl = 'http://127.0.0.1:8000';
const outDir = '.tmp/qa';
const workbook = '/Users/brunomartins/Desktop/Modulo Versa/Financeiro/Planilha de Custo - 2026.xlsx';
const workbookFallback = '/Users/brunomartins/Documents/Modulo Versa/Financeiro/Planilha de Custo - 2026.xlsx';
const statement = '/Users/brunomartins/Downloads/extrato-pj-05_03_2026_16h31m36s.pdf';
const fs = await import('node:fs');
const fileToUse = fs.existsSync(workbook) ? workbook : workbookFallback;
const email = `qa.${Date.now()}@draux.local`;
const password = 'Draux12345!';

async function openLatestAnalysis(page) {
  await page.getByRole('button', { name: 'Análises salvas' }).click();
  await page.waitForSelector('.saved-analysis-item');
  await page.locator('.saved-analysis-item').first().click();
  await page.waitForTimeout(1200);
}

const browser = await chromium.launch({ headless: true });
try {
  const desktopContext = await browser.newContext({ viewport: { width: 1440, height: 1400 } });
  const page = await desktopContext.newPage();
  await page.goto(baseUrl, { waitUntil: 'networkidle' });
  await page.screenshot({ path: `${outDir}/landing-desktop.png`, fullPage: true });

  await page.getByRole('button', { name: 'Criar conta' }).click();
  await page.getByLabel('Nome completo').fill('QA Visual Draux');
  await page.getByLabel('E-mail corporativo').fill(email);
  await page.getByLabel('Senha').fill(password);
  await page.getByRole('button', { name: 'Criar conta e acessar' }).click();
  await page.waitForSelector('text=Draux Inc. Workspace');
  await page.waitForLoadState('networkidle');

  const fileInputs = page.locator('input[type="file"]');
  await fileInputs.first().setInputFiles([fileToUse, statement]);
  await page.getByRole('button', { name: 'Analisar contexto e evidências' }).click();
  await page.waitForSelector('text=Valide o contexto antes de exportar', { timeout: 120000 });
  await page.waitForTimeout(2500);
  await page.screenshot({ path: `${outDir}/workspace-desktop-overview.png`, fullPage: true });

  await page.getByRole('tab', { name: 'DRE' }).click();
  await page.waitForTimeout(800);
  await page.screenshot({ path: `${outDir}/workspace-desktop-dre.png`, fullPage: true });

  await page.getByRole('tab', { name: 'Rastro' }).click();
  await page.waitForSelector('text=Rastreabilidade financeira');
  await page.waitForTimeout(1200);
  await page.screenshot({ path: `${outDir}/workspace-desktop-trace.png`, fullPage: true });

  await page.getByRole('button', { name: 'Aliases financeiros' }).click();
  await page.waitForSelector('text=Aliases financeiros');
  await page.waitForTimeout(800);
  await page.screenshot({ path: `${outDir}/workspace-desktop-aliases.png`, fullPage: true });
  await page.keyboard.press('Escape');
  await page.waitForTimeout(400);

  const statePath = `${outDir}/auth-state.json`;
  await desktopContext.storageState({ path: statePath });
  await desktopContext.close();

  const mobileContext = await browser.newContext({ ...devices['iPhone 13'], storageState: statePath });
  const mobilePage = await mobileContext.newPage();
  await mobilePage.goto(baseUrl, { waitUntil: 'networkidle' });
  await mobilePage.screenshot({ path: `${outDir}/workspace-mobile-home.png`, fullPage: true });
  await openLatestAnalysis(mobilePage);
  await mobilePage.getByRole('tab', { name: 'DRE' }).click();
  await mobilePage.waitForTimeout(800);
  await mobilePage.screenshot({ path: `${outDir}/workspace-mobile-dre.png`, fullPage: true });
  await mobilePage.getByRole('tab', { name: 'Rastro' }).click();
  await mobilePage.waitForTimeout(1200);
  await mobilePage.screenshot({ path: `${outDir}/workspace-mobile-trace.png`, fullPage: true });
  await mobilePage.getByRole('button', { name: 'Aliases financeiros' }).click();
  await mobilePage.waitForTimeout(800);
  await mobilePage.screenshot({ path: `${outDir}/workspace-mobile-aliases.png`, fullPage: true });
  await mobileContext.close();
} finally {
  await browser.close();
}
