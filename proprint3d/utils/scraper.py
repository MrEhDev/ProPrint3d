import cloudscraper
from bs4 import BeautifulSoup
import re

# =====================================================================
# MÓDULO: scraper.py
# Propósito: Extraer metadatos de MakerWorld dado un enlace.
# Razón de la estructura: Aísla la lógica HTTP/Scraping de las vistas.
# Usa BeautifulSoup para parsear HTML de forma robusta.
# NOTA: Se usa cloudscraper para evitar bloqueos 403 de Cloudflare.
# =====================================================================

def scrape_makerworld(url):
    """
    Función que realiza un GET a una URL de MakerWorld y extrae datos básicos.
    
    Parámetros:
    - url (str): Enlace a MakerWorld.
    
    Retorna un diccionario con title, description e image_url.
    """
    
    try:
        # Usamos cloudscraper en lugar de requests
        scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True})
        response = scraper.get(url, timeout=15)
        response.raise_for_status() # Lanza excepción si el status no es 200 OK
        
        # -------------------------------------------------------------
        # 2. Análisis del DOM HTML
        # Razón: BeautifulSoup permite navegar el árbol DOM y buscar tags
        # open-graph (og:title, og:image) que suelen ser precisos para el scraping.
        # -------------------------------------------------------------
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Intentamos obtener los metadatos de OpenGraph (diseñados para compartir en redes)
        og_title = soup.find('meta', property='og:title')
        og_image = soup.find('meta', property='og:image')
        og_desc = soup.find('meta', property='og:description')
        
        title = og_title['content'] if og_title else ''
        image_url = og_image['content'] if og_image else ''
        description = og_desc['content'] if og_desc else ''
        
        # Fallback si no hay og:title: buscar el <title> de la página
        if not title:
            page_title = soup.find('title')
            title = page_title.text if page_title else 'Modelo MakerWorld Desconocido'
            
        # -------------------------------------------------------------
        # 3. Limpieza de Cadenas (Regex) y Traducción
        # -------------------------------------------------------------
        from deep_translator import GoogleTranslator
        translator = GoogleTranslator(source='auto', target='es')
        
        # Quitar el sufijo genérico de MakerWorld
        title = title.replace(" - Free 3D Print Model - MakerWorld", "")
        title = title.replace(" - MakerWorld", "")
        
        # Limpiar frase genérica de la descripción
        if description:
            desc_clean = re.sub(r"Download this free 3D print file designed by [^.]+\.", "", description).strip()
            # Traducir descripción (solo si hay contenido)
            try:
                description = translator.translate(desc_clean[:4000]) # Límite de la API
            except:
                description = desc_clean
                
        # Traducir título
        if title:
            try:
                title = translator.translate(title)
            except:
                pass
            
        return {
            "success": True,
            "title": title,
            "description": description,
            "image_url": image_url,
            "url": url
        }
        
    except Exception as e:
        # En caso de error (timeout, 404, etc), devolvemos el error amigable
        return {
            "success": False,
            "error": str(e)
        }
