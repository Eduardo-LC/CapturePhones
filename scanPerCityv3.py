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
    """Atualiza o tempo da última interação do usuário (mouse ou teclado)."""
    global last_activity_time, activity_detected
    last_activity_time = time.time()
    activity_detected = True

# Configura os listeners para detectar quando o usuário mexe o mouse ou digita
mouse_listener = mouse.Listener(on_move=on_activity, on_click=on_activity)
keyboard_listener = keyboard.Listener(on_press=on_activity)
mouse_listener.start()
keyboard_listener.start()

def setup_driver():
    """Configura o WebDriver do Chrome para acessar o PlugShare e capturar logs de rede."""
    chrome_options = Options()
    chrome_options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )

    # 🔴 Limpa os logs de rede antes de começar
    driver.get_log("performance")
    
    return driver

def wait_for_user_search(driver, timeout=5):
    """Aguarda o usuário digitar a cidade e ficar 10 segundos inativo."""
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

def extract_latest_establishments_from_logs(driver):
    """Aguarda e captura a última requisição `locations/region`, garantindo que seja a mais recente."""
    print("🔍 Aguardando a última requisição de `locations/region` para capturar os dados corretos...")

    attempts = 0
    latest_request = None
    latest_request_id = None
    establishments_data = None

    while attempts < 10:  # 🔴 Aguarda até 10 tentativas (tempo suficiente para a nova requisição aparecer)
        logs = driver.get_log("performance")
        region_requests = []

        for entry in logs:
            try:
                message = json.loads(entry["message"])["message"]
                if message.get("method") == "Network.responseReceived":
                    url = message["params"]["response"]["url"]
                    if "locations/region" in url:
                        region_requests.append((url, message["params"]["requestId"]))  # 🔴 Guarda todas as requisições
            except Exception:
                continue

        if region_requests:
            latest_request, latest_request_id = region_requests[-1]  # 🔴 Pega sempre a mais recente
            print(f"✅ Capturando a última requisição de `locations/region`: {latest_request}")

            # Obtém os dados do corpo da resposta
            response = driver.execute_cdp_cmd("Network.getResponseBody", {"requestId": latest_request_id})
            establishments_data = json.loads(response["body"])

            break  # Sai do loop assim que capturar a requisição correta

        print("⏳ Aguardando a última requisição de `locations/region`...")
        time.sleep(2)
        attempts += 1

    if not establishments_data:
        print("❌ Não foi possível capturar os estabelecimentos corretos.")
        return []

    return establishments_data

def extract_phone_from_page(driver):
    """Obtém o número de telefone de um estabelecimento carregado na página."""
    try:
        time.sleep(1.4)
        phone_element = driver.find_element(By.XPATH, "//a[contains(@href, 'tel:')]")
        return phone_element.text.strip()
    except:
        return "Telefone não encontrado"

def save_partial_result(city, name, phone):
    """Salva cada número imediatamente após extração para evitar perda de dados."""
    filename = f"{city.replace(' ', '_')}_phones.txt"
    with open(filename, "a", encoding="utf-8") as f:
        f.write(f"{name} - {phone}\n")
    print(f"✅ Salvo: {name} - {phone}")

def main():
    driver = setup_driver()
    driver.get("https://www.plugshare.com/")
    time.sleep(1.4)
    
    # Aguarda o usuário pesquisar a cidade
    city_name = wait_for_user_search(driver)

    # Captura os estabelecimentos diretamente da última requisição de `locations/region`
    establishments = extract_latest_establishments_from_logs(driver)

    if not establishments:
        print("❌ Nenhum estabelecimento encontrado.")
        driver.quit()
        return

    print(f"✅ {len(establishments)} estabelecimentos encontrados.")

    # 🔴 Adicionando logs para garantir que todos os estabelecimentos estão sendo processados
    processed_count = 0

    # Obtém os números de telefone acessando cada URL na página
    for est in establishments:
        name = est.get("name", "Nome não encontrado")
        detail_url = est.get("url", "")
        
        if not detail_url:
            print(f"⚠️ Sem URL para {name}, pulando...")
            continue
        
        print(f"🔍 Acessando {name}: {detail_url}")
        
        driver.get(detail_url)
        phone = extract_phone_from_page(driver)
        save_partial_result(city_name, name, phone)

        processed_count += 1

    print(f"✅ Processamento concluído: {processed_count}/{len(establishments)} estabelecimentos salvos.")

    driver.quit()

if __name__ == "__main__":
    main()
