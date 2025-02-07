import time
import json
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

def setup_driver():
    """
    Configura o WebDriver do Chrome para capturar os logs de rede e acessar o PlugShare.
    """
    chrome_options = Options()
    # Comente a linha abaixo para ver o navegador durante a execução
    # chrome_options.add_argument("--headless")
    chrome_options.add_argument("--ignore-certificate-errors")
    chrome_options.add_argument("--allow-running-insecure-content")
    chrome_options.add_argument("--disable-web-security")

    # Habilita logs de performance para capturar as URLs das requisições da página
    chrome_options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )
    return driver

def wait_for_user_search(driver, timeout=10):
    """
    Aguarda o usuário digitar a cidade e espera 10 segundos de inatividade.
    """
    print("Digite a cidade no PlugShare e aguarde 10 segundos após a última entrada.")

    search_box = driver.find_element(By.CSS_SELECTOR, 'input[type="search"]')

    # Aguarda até que o usuário digite algo
    last_text = ""
    inactive_time = 0
    while inactive_time < timeout:
        current_text = search_box.get_attribute("value").strip()
        if current_text != last_text:
            last_text = current_text
            inactive_time = 0  # Resetar o tempo se houver mudança
        else:
            inactive_time += 1
        time.sleep(1)

    print(f"Pesquisa detectada: {last_text}")
    search_box.send_keys(Keys.RETURN)  # Simula Enter para confirmar a busca
    return last_text

def get_cookies_from_browser(driver):
    """
    Captura os cookies da sessão do navegador para serem usados nas requisições.
    """
    cookies = driver.get_cookies()
    return {cookie['name']: cookie['value'] for cookie in cookies}

def get_region_url_from_logs(driver):
    """
    Captura a URL 'locations/region' dos logs de rede do Selenium.
    """
    logs = driver.get_log("performance")
    region_url = None
    for entry in logs:
        try:
            message = json.loads(entry["message"])["message"]
            if message.get("method") == "Network.responseReceived":
                url = message["params"]["response"]["url"]
                if "locations/region" in url:  # Captura a URL correta
                    region_url = url
                    break
        except Exception:
            continue
    return region_url

def fetch_establishments(region_url, cookies):
    """
    Faz uma requisição GET para a URL capturada dos logs e retorna o JSON com os estabelecimentos.
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36"
        }
        response = requests.get(region_url, headers=headers, cookies=cookies)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Erro ao acessar a region URL: HTTP {response.status_code}")
            return []
    except Exception as e:
        print("Erro ao fazer requisição para region URL:", e)
        return []

def fetch_establishment_details(detail_url, cookies):
    """
    Faz uma requisição GET para obter detalhes de um estabelecimento.
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36"
        }
        response = requests.get(detail_url, headers=headers, cookies=cookies)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Erro ao acessar detalhes ({detail_url}): HTTP {response.status_code}")
            return None
    except Exception as e:
        print(f"Erro na requisição para {detail_url}: {e}")
        return None

def extract_phone(details):
    """
    Extrai o telefone do JSON de detalhes do estabelecimento.
    """
    phone = details.get("e164_phone_number") or details.get("formatted_phone_number")
    return phone if phone else "Telefone não encontrado"

def save_results(city, results):
    """
    Salva os resultados (nome e telefone) em um arquivo de texto.
    """
    filename = f"{city.replace(' ', '_')}_phones.txt"
    with open(filename, "w", encoding="utf-8") as f:
        for res in results:
            f.write(f"{res['name']} - {res['phone']}\n")
    print(f"Resultados salvos no arquivo: {filename}")

def main():
    driver = setup_driver()
    driver.get("https://www.plugshare.com/")
    time.sleep(3)
    
    # Aguarda o usuário pesquisar a cidade
    city_name = wait_for_user_search(driver)

    # Captura os cookies da sessão para evitar o erro 401
    cookies = get_cookies_from_browser(driver)

    # Captura a URL correta 'locations/region' dos logs de rede
    region_url = get_region_url_from_logs(driver)
    if not region_url:
        print("Não foi possível capturar a URL da pesquisa nos logs de rede. Encerrando.")
        driver.quit()
        return
    print(f"Region URL encontrada: {region_url}")
    
    # Obtém os estabelecimentos via API usando os cookies capturados
    establishments_data = fetch_establishments(region_url, cookies)
    
    # Verifica a estrutura da resposta
    if isinstance(establishments_data, list):
        establishments = establishments_data
    else:
        print("Estrutura de dados inesperada.")
        driver.quit()
        return

    print(f"{len(establishments)} estabelecimentos encontrados.")
    
    # Para cada estabelecimento, obter os detalhes e extrair o telefone
    results = []
    for est in establishments:
        name = est.get("name", "Nome não encontrado")
        detail_url = est.get("url")
        if detail_url:
            details = fetch_establishment_details(detail_url, cookies)
            phone = extract_phone(details) if details else "Detalhes não encontrados"
        else:
            phone = "URL não encontrada"
        results.append({"name": name, "phone": phone})
    
    save_results(city_name, results)
    driver.quit()

if __name__ == "__main__":
    main()
