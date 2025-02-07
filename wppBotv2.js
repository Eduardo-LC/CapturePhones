const puppeteer = require('puppeteer'), fs = require('fs'), path = require('path'), readline = require('readline');

const askQuestion = query => new Promise(resolve => readline.createInterface({
  input: process.stdin, output: process.stdout
}).question(query, ans => (resolve(ans), process.stdin.destroy())));

const cleanPhoneNumber = phone => phone.replace(/\D/g, '').replace(/^([^55])/, '55$1');

(async () => {
  const browser = await puppeteer.connect({ browserURL: 'http://localhost:9222' });
  const waPage = (await browser.pages()).find(p => p.url().includes('web.whatsapp.com'));
  if (!waPage) return console.error('Nenhuma aba do WhatsApp Web encontrada.'), process.exit(1);

  console.log("WhatsApp Web detectado! Iniciando automação...");

  const cityName = (await askQuestion('Digite o nome da cidade (sem extensão .json): ')).trim();
  if (!cityName) return console.error('Nome da cidade não informado.'), process.exit(1);

  const filePath = path.join(__dirname, 'numPerCity', `${cityName}.json`);
  if (!fs.existsSync(filePath)) return console.error(`Arquivo ${filePath} não encontrado.`), process.exit(1);

  const data = JSON.parse(fs.readFileSync(filePath, 'utf8'));
  if (!data.establishments || !data.numbers || data.establishments.length !== data.numbers.length)
    return console.error('JSON inválido.'), process.exit(1);

  for (let i = 0; i < data.establishments.length; i++) {
    const establishment = data.establishments[i], number = cleanPhoneNumber(data.numbers[i]);
    if (!number) { console.log(`Número inválido para ${establishment}. Pulando.`); continue; }

    console.log(`Enviando mensagem para ${establishment} (${number})`);
    await waPage.goto(`https://web.whatsapp.com/send/?phone=%2B${number}&text&type=phone_number&app_absent=0`);

    try {
      await waPage.waitForSelector('footer div[contenteditable="true"]', { visible: true, timeout: 15000 });
      await waPage.evaluate(() => document.querySelector('footer div[contenteditable="true"]').focus());

      const message = `Olá, ${establishment}! Estamos entrando em contato para apresentar nossos serviços e novidades.`;
      await waPage.type('footer div[contenteditable="true"]', message, { delay: 100 });
      await waPage.keyboard.press('Enter');

      console.log(`Mensagem enviada para ${establishment} (${number}).`);
    } catch (error) {
      console.error(`Erro ao enviar mensagem para ${establishment} (${number}):`, error.message);
    }

    // **Tempo ajustado para evitar bloqueios**
    await new Promise(resolve => setTimeout(resolve, 5000));
  }

  console.log("Automação concluída.");
  process.exit(0);
})();
