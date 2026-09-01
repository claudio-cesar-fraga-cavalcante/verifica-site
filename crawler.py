import asyncio
import logging
from urllib.parse import urlparse
from typing import Optional, List, Dict, Any
from playwright.async_api import async_playwright
import database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("crawler")

def extrair_dominio_raiz(domain: str) -> str:
    """Extrai o domínio raiz de um hostname (ex: www.infomoney.com.br -> infomoney.com.br)."""
    domain = domain.split(":")[0].lower() # Remove porta se houver
    partes = domain.split(".")
    if len(partes) >= 2:
        # Trata extensões duplas comuns como .com.br, .org.br
        if len(partes) >= 3 and partes[-2] in ["com", "org", "net", "gov", "edu"]:
            return ".".join(partes[-3:])
        return ".".join(partes[-2:])
    return domain

async def analisar_site_background(acesso_id: int, target_url: str, db_path: Optional[str] = None) -> None:
    """
    Acessa a URL em modo stealth usando Playwright, intercepta todas as chamadas em segundo plano
    (domínios de terceiros, trackers, recursos) e persiste os resultados no SQLite.
    """
    logger.info(f"[Acesso #{acesso_id}] Iniciando inspeção stealth para URL: {target_url}")
    
    parsed_target = urlparse(target_url)
    main_domain = parsed_target.netloc
    root_domain = extrair_dominio_raiz(main_domain)
    
    captured_requests: List[Dict[str, Any]] = []
    urls_vistas = set()

    try:
        async with async_playwright() as p:
            # Lança o Chromium em modo headless com flags para evitar detecção (stealth)
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-infobars",
                    "--window-position=0,0",
                    "--ignore-certificate-errors",
                ]
            )
            
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                locale="pt-BR",
                timezone_id="America/Sao_Paulo"
            )
            
            # Script stealth para ocultar navigator.webdriver
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)
            
            page = await context.new_page()

            # Callback para interceptar cada requisição disparada na página
            def handle_request(request):
                req_url = request.url
                if req_url.startswith(("http://", "https://")) and req_url not in urls_vistas:
                    urls_vistas.add(req_url)
                    req_parsed = urlparse(req_url)
                    req_domain = req_parsed.netloc.split(":")[0].lower()
                    req_root_domain = extrair_dominio_raiz(req_domain)
                    
                    # Considera domínio de terceiro se for diferente do domínio raiz do site acessado
                    eh_terceiro = (req_root_domain != root_domain)
                    
                    captured_requests.append({
                        "url_requisicao": req_url,
                        "dominio": req_domain,
                        "tipo_recurso": request.resource_type,
                        "eh_terceiro": eh_terceiro
                    })

            page.on("request", handle_request)

            try:
                # Navega até a página aguardando até que o DOM esteja carregado
                await page.goto(target_url, wait_until="domcontentloaded", timeout=20000)
                # Aguarda 6 segundos adicionais para capturar requisições assíncronas / scripts em background
                await page.wait_for_timeout(6000)
            except Exception as nav_err:
                logger.warning(f"[Acesso #{acesso_id}] Aviso na navegação: {nav_err}")
            
            await browser.close()

        # Salva no banco de dados SQLite
        if captured_requests:
            database.salvar_requisicoes_background(acesso_id, captured_requests, db_path=db_path)
        
        dominios_terceiros_unicos = set(
            req["dominio"] for req in captured_requests if req["eh_terceiro"]
        )
        
        total_bg = len(captured_requests)
        total_terceiros = len(dominios_terceiros_unicos)
        
        logger.info(f"[Acesso #{acesso_id}] Inspeção concluída. Total requisições: {total_bg}, Domínios de terceiros: {total_terceiros}")
        database.atualizar_status_acesso(
            acesso_id=acesso_id,
            status_analise="concluido",
            total_bg=total_bg,
            total_terceiros=total_terceiros,
            db_path=db_path
        )
        
    except Exception as e:
        logger.error(f"[Acesso #{acesso_id}] Erro na inspeção stealth: {e}", exc_info=True)
        database.atualizar_status_acesso(
            acesso_id=acesso_id,
            status_analise="erro",
            total_bg=0,
            total_terceiros=0,
            db_path=db_path
        )

def executar_analise_background(acesso_id: int, target_url: str, db_path: Optional[str] = None) -> None:
    """Wrapper síncrono para execução segura em threadpool via BackgroundTasks do FastAPI."""
    try:
        asyncio.run(analisar_site_background(acesso_id, target_url, db_path))
    except Exception as err:
        logger.error(f"[Acesso #{acesso_id}] Erro ao rodar asyncio no wrapper: {err}", exc_info=True)
        database.atualizar_status_acesso(
            acesso_id=acesso_id,
            status_analise="erro",
            total_bg=0,
            total_terceiros=0,
            db_path=db_path
        )
