import time
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from pynput import mouse, keyboard
from webdriver_manager.chrome import ChromeDriverManager

# Variáveis para detectar inatividade
last_activity_time = time.time()
activity_detected = False

def on_activity(*args):
    """
    Callback para detectar atividade do usuário (mouse ou teclado).
    Atualiza o tempo da última interação.
    """
    global last_activity_time, activity_detected
    last_activity_time = time.time()
    activity_detected = True

# Configura os listeners para detectar quando o usuário mexe o mouse ou digita
mouse_listener = mouse.Listener(on_move=on_activity, on_click=on_activity)
keyboard_listener = keyboard.Listener(on_press=on_activity)
mouse_listener.start()
keyboard_listener.start()

def setup_driver():
    """
    Configura o WebDriver do Chrome para acessar o PlugShare e capturar logs de rede.
    """
    chrome_options = Options()
    chrome_options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )
    return driver

def wait_for_user_search(driver, timeout=10):
    """
    Aguarda o usuário digitar a cidade e espera 10 segundos de inatividade (sem teclado e mouse).
    """
    print("Digite a cidade no PlugShare. O script continuará após 10 segundos de inatividade.")

    search_box = driver.find_element(By.CSS_SELECTOR, 'input[type="search"]')

    last_text = ""
    while not search_box.get_attribute("value").strip():
        time.sleep(1)

    print("Pesquisa detectada. Aguardando inatividade...")

    global last_activity_time, activity_detected
    activity_detected = False

    while time.time() - last_activity_time < timeout:
        time.sleep(1)

    print("Usuário inativo por 10 segundos. Agora aguardando seleção da cidade.")

    # Aguarda o usuário clicar em uma cidade para gerar a URL correta
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "a[data-testid='location-link']"))
        )
        print("Cidade selecionada. Continuando o fluxo.")
    except:
        print("⚠️ A cidade não foi selecionada corretamente. Verifique se você clicou na cidade.")

    return search_box.get_attribute("value").strip()

def extract_establishments_from_logs(driver):
    """
    Captura os dados dos estabelecimentos diretamente dos logs de rede do Selenium, sem precisar de novas requisições.
    """
    print("🔍 Capturando os dados diretamente dos logs de rede...")

    logs = driver.get_log("performance")
    establishments_data = None

    for entry in logs:
        try:
            message = json.loads(entry["message"])["message"]
            if message.get("method") == "Network.responseReceived":
                url = message["params"]["response"]["url"]
                if "locations/region" in url:  # Essa requisição contém os estabelecimentos
                    request_id = message["params"]["requestId"]
                    response = driver.execute_cdp_cmd("Network.getResponseBody", {"requestId": request_id})
                    establishments_data = json.loads(response["body"])  # Converte corretamente para JSON
                    print(f"✅ Dados da região capturados dos logs de rede: {url}")
                    break
        except Exception as e:
            continue

    if not establishments_data:
        print("❌ Não foi possível capturar os estabelecimentos dos logs de rede.")
        return []

    return establishments_data

def extract_phone_from_page(driver):
    """
    Obtém o número de telefone de um estabelecimento carregado na página.
    """
    try:
        time.sleep(3)
        phone_element = driver.find_element(By.XPATH, "//a[contains(@href, 'tel:')]")
        return phone_element.text.strip()
    except:
        return "Telefone não encontrado"

def save_results(city, results):
    """
    Salva os resultados (nome e telefone) em um arquivo de texto.
    """
    filename = f"{city.replace(' ', '_')}_phones.txt"
    with open(filename, "w", encoding="utf-8") as f:
        for res in results:
            f.write(f"{res['name']} - {res['phone']}\n")
    print(f"✅ Resultados salvos no arquivo: {filename}")

def main():
    driver = setup_driver()
    driver.get("https://www.plugshare.com/")
    time.sleep(3)
    
    # Aguarda o usuário pesquisar a cidade
    city_name = wait_for_user_search(driver)

    # Captura os estabelecimentos diretamente dos logs de rede
    establishments = extract_establishments_from_logs(driver)

    if not establishments:
        print("❌ Nenhum estabelecimento encontrado.")
        driver.quit()
        return

    print(f"✅ {len(establishments)} estabelecimentos encontrados.")

    # Obtém os números de telefone acessando cada URL na página
    results = []
    for est in establishments:
        name = est.get("name", "Nome não encontrado")
        detail_url = est.get("url", "")
        driver.get(detail_url)
        phone = extract_phone_from_page(driver)
        results.append({"name": name, "phone": phone})

    save_results(city_name, results)
    driver.quit()

if __name__ == "__main__":
    main()
