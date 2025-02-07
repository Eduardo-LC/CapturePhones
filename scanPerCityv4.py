import time
import json
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# Nome da pasta onde serão salvos os arquivos
FOLDER_NAME = "numPerCity"

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

def inject_continue_button(driver):
    """Injeta um botão visível na página para o usuário clicar e continuar."""
    js_script = """
    (function() {
        var btn = document.createElement("button");
        btn.innerHTML = "Continuar";
        btn.style.position = "fixed";
        btn.style.bottom = "20px";
        btn.style.right = "20px";
        btn.style.padding = "15px 30px";
        btn.style.fontSize = "18px";
        btn.style.fontWeight = "bold";
        btn.style.backgroundColor = "#FF5722";
        btn.style.color = "white";
        btn.style.border = "none";
        btn.style.borderRadius = "8px";
        btn.style.cursor = "pointer";
        btn.style.zIndex = "999999";  
        btn.style.opacity = "1";  
        btn.style.boxShadow = "0px 4px 10px rgba(0, 0, 0, 0.3)";
        btn.id = "continueButton";
        document.body.appendChild(btn);
        
        btn.onclick = function() {
            btn.innerHTML = "Aguardando...";
            btn.disabled = true;
            window.continueScript = true;
        };
    })();
    """
    driver.execute_script(js_script)

def wait_for_user_click(driver):
    """Espera até que o usuário clique no botão para continuar."""
    print("🔹 Clique no botão 'Continuar' na página do PlugShare para prosseguir.")

    while True:
        result = driver.execute_script("return window.continueScript || false;")
        if result:
            break
        time.sleep(1)

    print("✅ Usuário clicou no botão. Continuando o fluxo.")

def get_city_name(driver):
    """Obtém o nome da cidade digitada no campo de pesquisa."""
    try:
        search_box = driver.find_element(By.CSS_SELECTOR, 'input[type="search"]')
        city_name = search_box.get_attribute("value").strip()
        return city_name if city_name else "Cidade_Desconhecida"
    except:
        return "Cidade_Desconhecida"

def extract_latest_establishments_from_logs(driver):
    """Captura a última requisição `locations/region` para garantir que seja a mais recente."""
    print("🔍 Capturando a última requisição de `locations/region` nos logs de rede...")

    attempts = 0
    latest_request = None
    latest_request_id = None
    establishments_data = None

    while attempts < 10:  # 🔴 Aguarda até 10 tentativas para capturar a requisição correta
        logs = driver.get_log("performance")
        region_requests = []

        for entry in logs:
            try:
                message = json.loads(entry["message"])["message"]
                if message.get("method") == "Network.responseReceived":
                    url = message["params"]["response"]["url"]
                    if "locations/region" in url:
                        request_id = message["params"]["requestId"]
                        region_requests.append((url, request_id))  # 🔴 Guarda todas as requisições válidas
            except Exception:
                continue

        if region_requests:
            latest_request, latest_request_id = region_requests[-1]  # 🔴 Sempre captura a última
            print(f"✅ Última requisição capturada: {latest_request}")

            # Aguarda um pequeno tempo para garantir que a resposta esteja disponível
            time.sleep(2)

            try:
                response = driver.execute_cdp_cmd("Network.getResponseBody", {"requestId": latest_request_id})
                establishments_data = json.loads(response["body"])
                break  # Sai do loop assim que capturar a requisição correta
            except Exception as e:
                print(f"⚠️ Erro ao capturar resposta de `{latest_request}`. Tentando novamente... ({e})")

        print("⏳ Aguardando a última requisição de `locations/region`...")
        time.sleep(2)
        attempts += 1

    if not establishments_data:
        print("❌ Não foi possível capturar os estabelecimentos corretos.")
        return []

    return establishments_data

def extract_phone_from_page(driver):
    """Obtém o número de telefone de um estabelecimento carregado na página."""
    print("📞 Tentando capturar o telefone...")

    try:
        # 🔹 Espera o carregamento total da página antes de tentar capturar o telefone
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "h1"))
        )
        
        print("✅ Página carregada com sucesso.")
        
        # 🔹 Aguarda 2 segundos antes de capturar o telefone (garante carregamento completo)
        time.sleep(2)

        # 🔹 Espera a presença do telefone na página (até 10s)
        phone_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//a[contains(@href, 'tel:')]"))
        )
        phone_number = phone_element.text.strip()
        if phone_number:
            print(f"✅ Número encontrado: {phone_number}")
            return phone_number

    except:
        print("⚠️ O número de telefone via `<a href='tel:'>` não foi encontrado.")

    return "Telefone não encontrado"

def save_partial_result(city, name, phone):
    """Salva os resultados em arquivos separados para números encontrados e não encontrados."""
    # 🔹 Garante que a pasta `numPerCity` existe
    if not os.path.exists(FOLDER_NAME):
        os.makedirs(FOLDER_NAME)

    # Define os arquivos corretos
    if phone != "Telefone não encontrado":
        filename = os.path.join(FOLDER_NAME, f"{city.replace(' ', '_')}.txt")  # Arquivo com números encontrados
    else:
        filename = os.path.join(FOLDER_NAME, f"{city.replace(' ', '_')}NoNums.txt")  # Arquivo com números não encontrados
    
    with open(filename, "a", encoding="utf-8") as f:
        f.write(f"{name} - {phone}\n")
    
    print(f"✅ Salvo em `{filename}`: {name} - {phone}")

def main():
    driver = setup_driver()
    driver.get("https://www.plugshare.com/")
    time.sleep(3)  # 🔹 Aguarda o carregamento inicial da página

    try:
        inject_continue_button(driver)  # 🔹 Adiciona o botão "Continuar" na página
        wait_for_user_click(driver)  # 🔹 Aguarda o usuário clicar no botão "Continuar"

        city_name = get_city_name(driver)  # 🔹 Obtém o nome da cidade digitada
        print(f"🏙️ Cidade capturada: {city_name}")

        establishments = extract_latest_establishments_from_logs(driver)

        if not establishments:
            print("❌ Nenhum estabelecimento encontrado.")
            return

        print(f"✅ {len(establishments)} estabelecimentos encontrados.")

        processed_count = 0

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

    finally:
        driver.quit()

if __name__ == "__main__":
    main()
