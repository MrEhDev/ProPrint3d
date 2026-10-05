import cloudscraper
import requests
from bs4 import BeautifulSoup
import re
from deep_translator import GoogleTranslator

# =====================================================================
# MÓDULO: scraper.py
# Propósito: Extraer metadatos de MakerWorld dado un enlace.
# Razón de la estructura: 
# 1. Utiliza la API oficial interna de MakerWorld para evitar bloqueos 403.
# 2. Extrae título, descripción, imagen de portada, peso estimado y tiempo.
# 3. Traduce automáticamente título y descripción al español.
# 4. Fallback con CloudScraper y parseo OpenGraph si la API no está disponible.
# =====================================================================

def scrape_makerworld(url):
    """
    Función que realiza la extracción de datos desde una URL de MakerWorld.
    
    Parámetros:
    - url (str): Enlace a MakerWorld.
    
    Retorna un diccionario con title, description, image_url, weight_grams,
    print_time_hours, print_time_minutes y url.
    """
    try:
        # 1. Extraer ID del modelo si está presente en la URL (ej. /models/3301874...)
        match = re.search(r'models/(\d+)', url)
        design_id = match.group(1) if match else None
        
        title = ""
        image_url = ""
        description = ""
        weight_grams = None
        print_time_hours = None
        print_time_minutes = None

        # Intento 1: API REST directa de MakerWorld (altamente fiable y sin bloqueos 403)
        if design_id:
            api_url = f"https://makerworld.com/api/v1/design-service/design/{design_id}"
            api_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
                "Accept": "application/json, text/plain, */*",
                "Referer": f"https://makerworld.com/en/models/{design_id}",
                "Origin": "https://makerworld.com"
            }
            try:
                resp = requests.get(api_url, headers=api_headers, timeout=12)
                if resp.status_code == 200:
                    data = resp.json()
                    title = data.get('title') or ''
                    image_url = data.get('coverUrl') or data.get('cover') or ''
                    
                    # Limpieza del HTML en el resumen
                    raw_summary = data.get('summary') or ''
                    if raw_summary:
                        soup_desc = BeautifulSoup(raw_summary, 'html.parser')
                        description = soup_desc.get_text(separator='\n').strip()
                        
                    # Extraer peso estimado y tiempos de impresión de los perfiles
                    instances = data.get('instances') or []
                    if instances:
                        inst = instances[0]
                        w = inst.get('weight')
                        if w:
                            try:
                                weight_grams = float(w)
                            except (ValueError, TypeError):
                                pass
                                
                        pred = inst.get('prediction')
                        if pred:
                            try:
                                total_mins = int(pred) // 60
                                print_time_hours = total_mins // 60
                                print_time_minutes = total_mins % 60
                            except (ValueError, TypeError):
                                pass
            except Exception:
                pass

        # Intento 2: Fallback vía CloudScraper y parseo OpenGraph
        if not title:
            scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True})
            response = scraper.get(url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            og_title = soup.find('meta', property='og:title')
            og_image = soup.find('meta', property='og:image')
            og_desc = soup.find('meta', property='og:description')
            
            title = og_title['content'] if og_title else ''
            if not image_url and og_image:
                image_url = og_image['content']
            if not description and og_desc:
                description = og_desc['content']
                
            if not title:
                page_title = soup.find('title')
                title = page_title.text if page_title else 'Modelo MakerWorld'

        # Limpiezas generales de texto
        title = title.replace(" - Free 3D Print Model - MakerWorld", "").replace(" - MakerWorld", "").strip()
        if description:
            description = re.sub(r"Download this free 3D print file designed by [^.]+\.", "", description).strip()

        # Traducción automática al español
        translator = GoogleTranslator(source='auto', target='es')
        if description:
            try:
                description = translator.translate(description[:3500])
            except Exception:
                pass

        if title:
            try:
                title = translator.translate(title)
            except Exception:
                pass

        return {
            "success": True,
            "title": title,
            "description": description,
            "image_url": image_url,
            "weight_grams": weight_grams,
            "print_time_hours": print_time_hours,
            "print_time_minutes": print_time_minutes,
            "url": url
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
