const { test, expect, devices } = require("playwright/test");
const fs = require("node:fs");

const baseUrl = "http://127.0.0.1:8000";
const outDir = ".tmp/qa";
const workbookPrimary = "/Users/brunomartins/Desktop/Modulo Versa/Financeiro/Planilha de Custo - 2026.xlsx";
const workbookFallback = "/Users/brunomartins/Documents/Modulo Versa/Financeiro/Planilha de Custo - 2026.xlsx";
const statement = "/Users/brunomartins/Downloads/extrato-pj-05_03_2026_16h31m36s.pdf";
const workbook = fs.existsSync(workbookPrimary) ? workbookPrimary : workbookFallback;
const email = `qa.${Date.now()}@draux.local`;
const password = "Draux12345!";

async function openLatestAnalysis(page) {
  await page.getByRole("button", { name: "Análises salvas" }).click();
  await page.waitForSelector(".saved-analysis-item");
  await page.locator(".saved-analysis-item").first().click();
  await page.waitForTimeout(1200);
}

test("visual qa", async ({ browser }) => {
  const desktop = await browser.newContext({ viewport: { width: 1440, height: 1400 } });
  const page = await desktop.newPage();

  await page.goto(baseUrl, { waitUntil: "networkidle" });
  await page.screenshot({ path: `${outDir}/landing-desktop.png`, fullPage: true });

  await page.getByRole("button", { name: "Criar conta" }).click();
  await page.getByLabel("Nome completo").fill("QA Visual Draux");
  await page.getByLabel("E-mail corporativo").fill(email);
  await page.getByLabel("Senha").fill(password);
  await page.getByRole("button", { name: "Criar conta e acessar" }).click();

  await expect(page.getByText("Draux Inc. Workspace")).toBeVisible({ timeout: 120000 });

  const fileInputs = page.locator('input[type="file"]');
  await fileInputs.first().setInputFiles([workbook, statement]);
  await page.getByRole("button", { name: "Analisar contexto e evidências" }).click();

  await expect(page.getByText("Valide o contexto antes de exportar")).toBeVisible({ timeout: 120000 });
  await page.waitForTimeout(2500);
  await page.screenshot({ path: `${outDir}/workspace-desktop-overview.png`, fullPage: true });

  await page.getByRole("tab", { name: "DRE" }).click();
  await page.waitForTimeout(800);
  await page.screenshot({ path: `${outDir}/workspace-desktop-dre.png`, fullPage: true });

  await page.getByRole("tab", { name: "Rastro" }).click();
  await expect(page.getByText("Rastreabilidade financeira")).toBeVisible();
  await page.waitForTimeout(1200);
  await page.screenshot({ path: `${outDir}/workspace-desktop-trace.png`, fullPage: true });

  await page.getByRole("button", { name: "Aliases financeiros" }).click();
  await expect(page.getByText("Aliases financeiros")).toBeVisible();
  await page.waitForTimeout(800);
  await page.screenshot({ path: `${outDir}/workspace-desktop-aliases.png`, fullPage: true });
  await page.keyboard.press("Escape");
  await page.waitForTimeout(400);

  const storageState = await desktop.storageState();
  await desktop.close();

  const mobile = await browser.newContext({
    ...devices["iPhone 13"],
    storageState,
  });
  const mobilePage = await mobile.newPage();
  await mobilePage.goto(baseUrl, { waitUntil: "networkidle" });
  await mobilePage.screenshot({ path: `${outDir}/workspace-mobile-home.png`, fullPage: true });

  await openLatestAnalysis(mobilePage);
  await mobilePage.getByRole("tab", { name: "DRE" }).click();
  await mobilePage.waitForTimeout(800);
  await mobilePage.screenshot({ path: `${outDir}/workspace-mobile-dre.png`, fullPage: true });

  await mobilePage.getByRole("tab", { name: "Rastro" }).click();
  await mobilePage.waitForTimeout(1200);
  await mobilePage.screenshot({ path: `${outDir}/workspace-mobile-trace.png`, fullPage: true });

  await mobilePage.getByRole("button", { name: "Aliases financeiros" }).click();
  await mobilePage.waitForTimeout(800);
  await mobilePage.screenshot({ path: `${outDir}/workspace-mobile-aliases.png`, fullPage: true });

  await mobile.close();
});
