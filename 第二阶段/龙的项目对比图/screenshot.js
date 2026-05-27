const puppeteer = require('puppeteer');

(async () => {
  const browser = await puppeteer.launch({ headless: true });
  const page = await browser.newPage();
  await page.setViewport({ width: 1600, height: 900 });
  await page.goto('http://localhost:8899/%E5%AF%B9%E6%AF%94%E5%9B%BE-%E7%A0%94%E7%A9%B6%E8%8C%83%E5%BC%8F.html', {
    waitUntil: 'networkidle0'
  });
  await page.waitForSelector('.slide');
  await page.screenshot({
    path: 'C:/Honey/对比图-研究范式.png',
    clip: {
      x: 0,
      y: 0,
      width: 1600,
      height: 900
    }
  });
  await browser.close();
  console.log('Screenshot saved successfully');
})();
