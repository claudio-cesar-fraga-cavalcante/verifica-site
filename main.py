from fastapi import FastAPI, HTTPException, Query, status, BackgroundTasks
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
from typing import Optional, List

import database
import crawler
from schemas import AcessoCreate, AcessoResponse, AcessoListResponse, RequisicaoBackgroundResponse

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicializa o banco de dados SQLite e tabelas na inicialização da aplicação
    database.init_db()
    yield

app = FastAPI(
    title="Verifica Site API",
    description="API para registro, persistência, exibição e inspeção stealth de acessos a websites em segundo plano.",
    version="2.2.0",
    lifespan=lifespan
)

@app.post(
    "/acessos", 
    response_model=AcessoResponse, 
    status_code=status.HTTP_201_CREATED,
    summary="Receber e salvar dados de acesso a site",
    description="Recebe o payload JSON de outra aplicação com a URL, data/hora de acesso e explicação, e inicia a inspeção em modo stealth das requisições em segundo plano."
)
def criar_acesso(acesso: AcessoCreate, background_tasks: BackgroundTasks):
    novo_acesso = database.salvar_acesso(
        url=acesso.url,
        data_hora_acesso=acesso.data_hora_acesso,
        explicacao=acesso.explicacao
    )
    
    # Enfileira a tarefa assíncrona de crawler stealth em segundo plano (em threadpool isolada)
    background_tasks.add_task(
        crawler.executar_analise_background,
        acesso_id=novo_acesso["id"],
        target_url=acesso.url
    )
    
    return novo_acesso

@app.get(
    "/acessos", 
    response_model=AcessoListResponse,
    summary="Exibir acessos registrados",
    description="Retorna a lista de todos os acessos salvos no banco de dados SQLite com suporte a paginação, busca e contadores de chamadas ocultas."
)
def listar_acessos(
    limit: int = Query(default=100, ge=1, le=1000, description="Quantidade de registros por página"),
    offset: int = Query(default=0, ge=0, description="Índice inicial para paginação"),
    busca: Optional[str] = Query(default=None, description="Termo de busca para filtrar por URL ou explicação")
):
    resultado = database.listar_acessos(limit=limit, offset=offset, busca=busca)
    return resultado

@app.delete(
    "/acessos",
    summary="Excluir todos os registros",
    description="Exclui permanentemente todos os registros das tabelas de acessos e requisições em segundo plano."
)
def limpar_todos_acessos():
    resultado = database.limpar_todos_dados()
    return {
        "mensagem": "Todos os registros foram excluídos com sucesso.",
        "detalhes": resultado
    }

@app.get(
    "/acessos/{acesso_id}", 
    response_model=AcessoResponse,
    summary="Exibir acesso por ID",
    description="Retorna os detalhes de um acesso registrado especificando o seu ID."
)
def obter_acesso(acesso_id: int):
    acesso = database.obter_acesso_por_id(acesso_id)
    if not acesso:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Acesso com ID {acesso_id} não foi encontrado."
        )
    return acesso

@app.get(
    "/acessos/{acesso_id}/background",
    response_model=List[RequisicaoBackgroundResponse],
    summary="Exibir requisições de segundo plano capturadas",
    description="Retorna todas as chamadas HTTP/HTTPS (scripts de terceiros, trackers, CDNs) interceptadas em segundo plano para o acesso informado."
)
def listar_requisicoes_background(acesso_id: int):
    acesso = database.obter_acesso_por_id(acesso_id)
    if not acesso:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Acesso com ID {acesso_id} não foi encontrado."
        )
    return database.obter_requisicoes_background(acesso_id)

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def dashboard():
    html_content = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Verifica Site - Dashboard & Grafo de Conexões</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <!-- Vis.js Network para renderização em grafo 2D com fallback CDN -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/vis-network/9.1.2/standalone/umd/vis-network.min.js"></script>
    <script type="text/javascript">
        if (typeof vis === 'undefined') {
            document.write('<script src="https://unpkg.com/vis-network@9.1.2/standalone/umd/vis-network.min.js"><\/script>');
        }
    </script>
    <style>
        :root {
            --bg: #090d16;
            --card-bg: rgba(18, 24, 38, 0.75);
            --card-border: rgba(255, 255, 255, 0.08);
            --text: #f1f5f9;
            --text-secondary: #94a3b8;
            --accent: #6366f1;
            --accent-hover: #4f46e5;
            --accent-glow: rgba(99, 102, 241, 0.25);
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
            --purple: #a855f7;
            --input-bg: rgba(10, 15, 26, 0.6);
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }

        body {
            font-family: 'Plus Jakarta Sans', sans-serif;
            background-color: var(--bg);
            background-image: 
                radial-gradient(at 10% 10%, rgba(99, 102, 241, 0.15) 0px, transparent 50%),
                radial-gradient(at 90% 90%, rgba(16, 185, 129, 0.1) 0px, transparent 50%);
            color: var(--text);
            min-height: 100vh;
            padding: 2rem 1rem;
            display: flex;
            justify-content: center;
        }

        .container {
            width: 100%;
            max-width: 1300px;
            display: flex;
            flex-direction: column;
            gap: 2rem;
        }

        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 1rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid var(--card-border);
        }

        .brand { display: flex; align-items: center; gap: 0.75rem; }

        .brand-icon {
            width: 42px;
            height: 42px;
            background: linear-gradient(135deg, #6366f1, #a855f7);
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 1.2rem;
            box-shadow: 0 4px 12px var(--accent-glow);
        }

        h1 { font-size: 1.5rem; font-weight: 700; letter-spacing: -0.02em; }
        .subtitle { color: var(--text-secondary); font-size: 0.875rem; }

        .header-actions { display: flex; gap: 0.75rem; align-items: center; }

        .btn-secondary {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--card-border);
            color: var(--text);
            padding: 0.5rem 1rem;
            border-radius: 8px;
            text-decoration: none;
            font-size: 0.875rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
        }
        .btn-secondary:hover {
            background: rgba(255, 255, 255, 0.1);
            border-color: rgba(255, 255, 255, 0.2);
        }

        .btn-danger-soft {
            background: rgba(239, 68, 68, 0.1);
            border: 1px solid rgba(239, 68, 68, 0.3);
            color: #fca5a5;
        }
        .btn-danger-soft:hover {
            background: var(--danger);
            color: white;
            border-color: var(--danger);
            box-shadow: 0 4px 12px rgba(239, 68, 68, 0.3);
        }

        .grid {
            display: grid;
            grid-template-columns: 340px 1fr;
            gap: 1.5rem;
        }

        @media (max-width: 900px) {
            .grid { grid-template-columns: 1fr; }
        }

        .card {
            background: var(--card-bg);
            backdrop-filter: blur(12px);
            border: 1px solid var(--card-border);
            border-radius: 16px;
            padding: 1.5rem;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        }

        .card-title {
            font-size: 1.1rem;
            font-weight: 600;
            margin-bottom: 1.25rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .form-group {
            display: flex;
            flex-direction: column;
            gap: 0.4rem;
            margin-bottom: 1rem;
        }

        label {
            font-size: 0.8rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-secondary);
        }

        input, textarea {
            background: var(--input-bg);
            border: 1px solid var(--card-border);
            border-radius: 8px;
            padding: 0.75rem;
            color: var(--text);
            font-family: inherit;
            font-size: 0.9rem;
            outline: none;
            transition: border-color 0.2s;
        }
        input:focus, textarea:focus {
            border-color: var(--accent);
            box-shadow: 0 0 0 3px var(--accent-glow);
        }
        textarea { resize: vertical; min-height: 80px; }

        .btn-primary {
            background: linear-gradient(135deg, var(--accent), #4f46e5);
            color: white;
            border: none;
            border-radius: 8px;
            padding: 0.75rem 1.25rem;
            font-size: 0.9rem;
            font-weight: 600;
            cursor: pointer;
            width: 100%;
            transition: transform 0.1s, box-shadow 0.2s;
            box-shadow: 0 4px 14px var(--accent-glow);
        }
        .btn-primary:hover {
            transform: translateY(-1px);
            box-shadow: 0 6px 20px var(--accent-glow);
        }

        .search-bar { display: flex; gap: 0.5rem; margin-bottom: 1rem; }
        .search-bar input { flex: 1; }

        .stats-bar { display: flex; gap: 1rem; margin-bottom: 1rem; }
        .stat-item {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid var(--card-border);
            border-radius: 10px;
            padding: 0.75rem 1rem;
            flex: 1;
        }
        .stat-value { font-size: 1.4rem; font-weight: 700; color: var(--accent); }
        .stat-label { font-size: 0.75rem; color: var(--text-secondary); }

        .table-container {
            overflow-x: auto;
            border-radius: 10px;
            border: 1px solid var(--card-border);
        }

        table {
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            font-size: 0.85rem;
        }
        th {
            background: rgba(255, 255, 255, 0.03);
            padding: 0.85rem 1rem;
            font-weight: 600;
            color: var(--text-secondary);
            border-bottom: 1px solid var(--card-border);
        }
        td {
            padding: 0.85rem 1rem;
            border-bottom: 1px solid var(--card-border);
            vertical-align: middle;
        }
        tr:last-child td { border-bottom: none; }
        tr:hover td { background: rgba(255, 255, 255, 0.02); }

        .badge-id {
            background: rgba(99, 102, 241, 0.15);
            color: #818cf8;
            padding: 0.2rem 0.5rem;
            border-radius: 6px;
            font-weight: 600;
            font-size: 0.75rem;
        }

        .badge-status {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            padding: 0.25rem 0.6rem;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 600;
        }
        .status-processando {
            background: rgba(245, 158, 11, 0.15);
            color: var(--warning);
            border: 1px solid rgba(245, 158, 11, 0.3);
        }
        .status-concluido {
            background: rgba(16, 185, 129, 0.15);
            color: var(--success);
            border: 1px solid rgba(16, 185, 129, 0.3);
        }
        .status-erro {
            background: rgba(239, 68, 68, 0.15);
            color: var(--danger);
            border: 1px solid rgba(239, 68, 68, 0.3);
        }

        .spinner {
            width: 12px;
            height: 12px;
            border: 2px solid var(--warning);
            border-top-color: transparent;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }

        .url-link {
            color: #38bdf8;
            text-decoration: none;
            word-break: break-all;
            font-weight: 500;
        }
        .url-link:hover { text-decoration: underline; }

        .action-buttons {
            display: flex;
            gap: 0.35rem;
            flex-wrap: nowrap;
        }

        .btn-inspect {
            background: rgba(99, 102, 241, 0.15);
            border: 1px solid rgba(99, 102, 241, 0.3);
            color: #a5b4fc;
            padding: 0.35rem 0.65rem;
            border-radius: 6px;
            font-size: 0.75rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            white-space: nowrap;
        }
        .btn-inspect:hover {
            background: var(--accent);
            color: white;
        }

        .btn-graph {
            background: rgba(168, 85, 247, 0.15);
            border: 1px solid rgba(168, 85, 247, 0.35);
            color: #c084fc;
            padding: 0.35rem 0.65rem;
            border-radius: 6px;
            font-size: 0.75rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            white-space: nowrap;
        }
        .btn-graph:hover {
            background: var(--purple);
            color: white;
            box-shadow: 0 4px 12px rgba(168, 85, 247, 0.3);
        }

        /* Modal */
        .modal-overlay {
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0, 0, 0, 0.75);
            backdrop-filter: blur(8px);
            display: flex;
            align-items: center;
            justify-content: center;
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.25s ease;
            z-index: 1000;
            padding: 1rem;
        }
        .modal-overlay.open { opacity: 1; pointer-events: auto; }

        .modal-container {
            background: #111827;
            border: 1px solid var(--card-border);
            border-radius: 16px;
            width: 100%;
            max-width: 850px;
            max-height: 85vh;
            display: flex;
            flex-direction: column;
            box-shadow: 0 20px 50px rgba(0,0,0,0.6);
            transform: scale(0.95);
            transition: transform 0.25s ease;
        }
        .modal-overlay.open .modal-container { transform: scale(1); }

        .modal-header {
            padding: 1.25rem 1.5rem;
            border-bottom: 1px solid var(--card-border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .modal-title { font-size: 1.1rem; font-weight: 700; }
        .modal-close {
            background: transparent;
            border: none;
            color: var(--text-secondary);
            font-size: 1.5rem;
            cursor: pointer;
        }
        .modal-close:hover { color: var(--text); }

        .modal-body {
            padding: 1.5rem;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 1.25rem;
        }

        .domain-tag-list {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
        }
        .domain-tag {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--card-border);
            padding: 0.3rem 0.6rem;
            border-radius: 6px;
            font-size: 0.75rem;
            font-weight: 600;
            color: #cbd5e1;
        }
        .domain-tag.third-party {
            background: rgba(245, 158, 11, 0.1);
            border-color: rgba(245, 158, 11, 0.25);
            color: #fbbf24;
        }

        .explanation-text {
            color: #cbd5e1;
            font-size: 0.82rem;
            line-height: 1.4;
            max-width: 260px;
            word-break: break-word;
            white-space: normal;
        }

        .toast {
            position: fixed;
            bottom: 2rem;
            right: 2rem;
            background: var(--card-bg);
            border: 1px solid var(--success);
            color: var(--text);
            padding: 1rem 1.5rem;
            border-radius: 12px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
            display: flex;
            align-items: center;
            gap: 0.75rem;
            transform: translateY(100px);
            opacity: 0;
            transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            z-index: 1100;
        }
        .toast.show { transform: translateY(0); opacity: 1; }
        .empty-state { text-align: center; padding: 2rem 1rem; color: var(--text-secondary); }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="brand">
                <div class="brand-icon">VS</div>
                <div>
                    <h1>Verifica Site</h1>
                    <div class="subtitle">Inspeção Stealth & Visualização em Grafo de Terceiros</div>
                </div>
            </div>
            <div class="header-actions">
                <button onclick="confirmarLimparDados()" class="btn-secondary btn-danger-soft">
                    🗑️ Limpar Banco de Dados
                </button>
                <a href="/docs" target="_blank" class="btn-secondary">📘 Documentação Swagger</a>
            </div>
        </header>

        <div class="grid">
            <!-- Formulário de Envio (POST /acessos) -->
            <div class="card">
                <div class="card-title">
                    <span>⚡ Registrar & Inspecionar Site</span>
                </div>
                <form id="acessoForm">
                    <div class="form-group">
                        <label for="url">URL do Site</label>
                        <input type="url" id="url" required placeholder="https://www.infomoney.com.br" value="https://www.infomoney.com.br">
                    </div>
                    <div class="form-group">
                        <label for="data_hora_acesso">Data e Hora do Acesso</label>
                        <input type="text" id="data_hora_acesso" required placeholder="18/09/2026 17:30:01">
                    </div>
                    <div class="form-group">
                        <label for="explicacao">Explicação</label>
                        <textarea id="explicacao" required placeholder="este site refere-se a...">Auditoria de requisições em segundo plano e rastreadores ocultos.</textarea>
                    </div>
                    <button type="submit" class="btn-primary" id="btnSubmit">Enviar & Iniciar Inspeção</button>
                </form>
            </div>

            <!-- Tabela de Registros -->
            <div class="card">
                <div class="card-title">
                    <span>📊 Acessos & Chamadas em Background</span>
                </div>

                <div class="stats-bar">
                    <div class="stat-item">
                        <div class="stat-value" id="statTotal">0</div>
                        <div class="stat-label">Total Registrados</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value" style="color: var(--success);" id="statTerceiros">0</div>
                        <div class="stat-label">Terceiros Capturados</div>
                    </div>
                </div>

                <div class="search-bar">
                    <input type="text" id="searchInput" placeholder="Filtrar por URL ou explicação...">
                    <button type="button" class="btn-secondary" onclick="carregarAcessos()">Atualizar</button>
                </div>

                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>URL / Data</th>
                                <th>Explicação</th>
                                <th>Status Análise</th>
                                <th>Terceiros / Total BG</th>
                                <th>Ações</th>
                            </tr>
                        </thead>
                        <tbody id="tabelaBody">
                            <tr>
                                <td colspan="6" class="empty-state">Carregando dados...</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>

    <!-- Modal 1: Lista e Detalhes da Inspeção Background (Mantido Intacto) -->
    <div class="modal-overlay" id="modalOverlay">
        <div class="modal-container">
            <div class="modal-header">
                <div class="modal-title" id="modalTitle">Detalhamento de Requisições Ocultas</div>
                <button class="modal-close" onclick="fecharModal()">&times;</button>
            </div>
            <div class="modal-body" id="modalBody">
                <div class="empty-state">Carregando detalhes...</div>
            </div>
        </div>
    </div>

    <!-- Modal 2: Novo Mapa de Conexões em Grafo (Vis.js Network 2D) -->
    <div class="modal-overlay" id="modalGraphOverlay">
        <div class="modal-container" style="max-width: 1050px; min-height: 600px;">
            <div class="modal-header">
                <div class="modal-title" id="modalGraphTitle">🕸️ Mapa de Conexões em Grafo</div>
                <button class="modal-close" onclick="fecharModalGrafo()">&times;</button>
            </div>
            <div class="modal-body" style="padding: 0; display: flex; flex-direction: column; position: relative; overflow: hidden;">
                <div id="graphLegend" style="padding: 0.75rem 1.25rem; background: rgba(0,0,0,0.5); border-bottom: 1px solid var(--card-border); display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem; font-size: 0.8rem; z-index: 10;">
                    <div style="display: flex; gap: 1rem; align-items: center;">
                        <span><span style="display:inline-block; width:12px; height:12px; border-radius:50%; background:#a855f7; margin-right:4px;"></span> Site Principal</span>
                        <span><span style="display:inline-block; width:12px; height:12px; border-radius:50%; background:#f59e0b; margin-right:4px;"></span> Domínios de Terceiros</span>
                        <span><span style="display:inline-block; width:12px; height:12px; border-radius:50%; background:#0284c7; margin-right:4px;"></span> Recursos Próprios</span>
                    </div>
                    <div style="color: var(--text-secondary); font-weight: 600;" id="graphStats">0 Conexões Mapeadas</div>
                </div>
                <div id="networkCanvas" style="width: 100%; height: 520px; background: #0b0f19; cursor: grab; position: relative;"></div>
            </div>
        </div>
    </div>

    <div id="toast" class="toast">
        <span style="color: var(--success); font-size: 1.2rem;">✓</span>
        <span id="toastMessage">Registro salvo! Inspeção stealth iniciada em segundo plano.</span>
    </div>

    <script>
        let pollTimer = null;
        let networkInstance = null;

        function formatarDataAtual() {
            const agora = new Date();
            const dia = String(agora.getDate()).padStart(2, '0');
            const mes = String(agora.getMonth() + 1).padStart(2, '0');
            const ano = agora.getFullYear();
            const horas = String(agora.getHours()).padStart(2, '0');
            const mins = String(agora.getMinutes()).padStart(2, '0');
            const segs = String(agora.getSeconds()).padStart(2, '0');
            return `${dia}/${mes}/${ano} ${horas}:${mins}:${segs}`;
        }

        document.getElementById('data_hora_acesso').value = formatarDataAtual();

        function mostrarToast(msg) {
            const toast = document.getElementById('toast');
            document.getElementById('toastMessage').innerText = msg;
            toast.classList.add('show');
            setTimeout(() => toast.classList.remove('show'), 3500);
        }

        async function carregarAcessos() {
            const busca = document.getElementById('searchInput').value;
            const url = busca ? `/acessos?busca=${encodeURIComponent(busca)}` : '/acessos';
            
            try {
                const response = await fetch(url);
                const data = await response.json();
                
                document.getElementById('statTotal').innerText = data.total;
                
                let somaTerceiros = 0;
                let possuiProcessando = false;

                const tbody = document.getElementById('tabelaBody');
                
                if (!data.items || data.items.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="6" class="empty-state">Nenhum registro de acesso encontrado.</td></tr>';
                    document.getElementById('statTerceiros').innerText = "0";
                    return;
                }

                tbody.innerHTML = data.items.map(item => {
                    somaTerceiros += (item.total_dominios_terceiros || 0);
                    
                    let statusHtml = '';
                    if (item.status_analise === 'processando') {
                        possuiProcessando = true;
                        statusHtml = `<span class="badge-status status-processando"><div class="spinner"></div> Processando</span>`;
                    } else if (item.status_analise === 'concluido') {
                        statusHtml = `<span class="badge-status status-concluido">✓ Concluído</span>`;
                    } else {
                        statusHtml = `<span class="badge-status status-erro">⚠ Erro</span>`;
                    }

                    return `
                        <tr>
                            <td><span class="badge-id">#${item.id}</span></td>
                            <td>
                                <a href="${item.url}" target="_blank" class="url-link">${item.url}</a>
                                <div style="font-size: 0.75rem; color: var(--text-secondary); margin-top: 0.2rem;">${item.data_hora_acesso}</div>
                            </td>
                            <td>
                                <div class="explanation-text" title="${escapeHtml(item.explicacao)}">${escapeHtml(item.explicacao)}</div>
                            </td>
                            <td>${statusHtml}</td>
                            <td>
                                <strong>${item.total_dominios_terceiros || 0}</strong> domínios
                                <div style="font-size: 0.75rem; color: var(--text-secondary);">${item.total_requisicoes_bg || 0} reqs totais</div>
                            </td>
                            <td>
                                <div class="action-buttons">
                                    <button class="btn-inspect" onclick="abrirDetalhesBackground(${item.id}, '${escapeHtml(item.url)}')">
                                        🔍 Requisições
                                    </button>
                                    <button class="btn-graph" onclick="abrirGrafoBackground(${item.id}, '${escapeHtml(item.url)}')">
                                        🕸️ Grafo
                                    </button>
                                </div>
                            </td>
                        </tr>
                    `;
                }).join('');

                document.getElementById('statTerceiros').innerText = somaTerceiros;

                if (possuiProcessando) {
                    if (!pollTimer) {
                        pollTimer = setInterval(carregarAcessos, 3500);
                    }
                } else {
                    if (pollTimer) {
                        clearInterval(pollTimer);
                        pollTimer = null;
                    }
                }

            } catch (err) {
                console.error("Erro ao carregar acessos:", err);
            }
        }

        // Modal 1: Lista Mantida Intacta
        async function abrirDetalhesBackground(acessoId, url) {
            document.getElementById('modalTitle').innerText = `Requisições em Background (#${acessoId}): ${url}`;
            const modalBody = document.getElementById('modalBody');
            modalBody.innerHTML = '<div class="empty-state">Buscando requisições interceptadas...</div>';
            document.getElementById('modalOverlay').classList.add('open');

            try {
                const response = await fetch(`/acessos/${acessoId}/background`);
                const reqs = await response.json();

                if (!reqs || reqs.length === 0) {
                    modalBody.innerHTML = '<div class="empty-state">Nenhuma requisição em segundo plano gravada ainda. Aguarde o término da análise.</div>';
                    return;
                }

                const dominiosTerceiros = [...new Set(reqs.filter(r => r.eh_terceiro).map(r => r.dominio))];
                const dominiosProprios = [...new Set(reqs.filter(r => !r.eh_terceiro).map(r => r.dominio))];

                let html = `
                    <div>
                        <h4 style="font-size: 0.9rem; margin-bottom: 0.5rem; color: #fbbf24;">
                            🌐 Domínios de Terceiros Detectados (${dominiosTerceiros.length})
                        </h4>
                        <div class="domain-tag-list">
                            ${dominiosTerceiros.length > 0 
                                ? dominiosTerceiros.map(d => `<span class="domain-tag third-party">${escapeHtml(d)}</span>`).join('') 
                                : '<span style="color: var(--text-secondary); font-size: 0.8rem;">Nenhum domínio de terceiro detectado.</span>'}
                        </div>
                    </div>

                    <div>
                        <h4 style="font-size: 0.9rem; margin-bottom: 0.5rem; color: #38bdf8;">
                            🏠 Domínios Próprios (${dominiosProprios.length})
                        </h4>
                        <div class="domain-tag-list">
                            ${dominiosProprios.map(d => `<span class="domain-tag">${escapeHtml(d)}</span>`).join('')}
                        </div>
                    </div>

                    <div style="margin-top: 0.5rem;">
                        <h4 style="font-size: 0.9rem; margin-bottom: 0.75rem;">
                            📋 Todas as Requisições Interceptadas (${reqs.length})
                        </h4>
                        <div class="table-container" style="max-height: 350px;">
                            <table>
                                <thead>
                                    <tr>
                                        <th>Tipo</th>
                                        <th>Domínio</th>
                                        <th>URL Completa</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${reqs.map(r => `
                                        <tr>
                                            <td><span class="badge-id" style="font-size: 0.7rem;">${escapeHtml(r.tipo_recurso)}</span></td>
                                            <td><span class="${r.eh_terceiro ? 'domain-tag third-party' : 'domain-tag'}">${escapeHtml(r.dominio)}</span></td>
                                            <td style="word-break: break-all; font-size: 0.75rem; color: #cbd5e1;">${escapeHtml(r.url_requisicao)}</td>
                                        </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        </div>
                    </div>
                `;

                modalBody.innerHTML = html;

            } catch (err) {
                modalBody.innerHTML = `<div class="empty-state" style="color: var(--danger);">Erro ao carregar detalhes: ${escapeHtml(err.message)}</div>`;
            }
        }

        // Modal 2: Novo Grafo Interativo 2D
        async function abrirGrafoBackground(acessoId, url) {
            document.getElementById('modalGraphTitle').innerText = `🕸️ Mapa de Conexões: ${url}`;
            document.getElementById('modalGraphOverlay').classList.add('open');
            
            const container = document.getElementById('networkCanvas');
            container.innerHTML = '<div class="empty-state" style="padding-top: 5rem;">Gerando o mapa de rede em grafo...</div>';

            try {
                const response = await fetch(`/acessos/${acessoId}/background`);
                const reqs = await response.json();

                if (!reqs || reqs.length === 0) {
                    container.innerHTML = '<div class="empty-state" style="padding-top: 5rem;">Nenhuma conexão em segundo plano registrada ainda. Aguarde o término da análise.</div>';
                    document.getElementById('graphStats').innerText = "0 Conexões Mapeadas";
                    return;
                }

                // Se a biblioteca vis.js não estiver carregada (ex: offline ou CDN bloqueado), usa renderizador Canvas 2D
                if (typeof vis === 'undefined') {
                    renderizarGrafoCanvasFallback(container, mainDomain, domainCounts, domainIsThirdParty, reqs.length, countTerceiros);
                    return;
                }

                // Extrai o domínio principal
                let mainDomain = "Site Principal";
                try {
                    mainDomain = new URL(url).hostname.replace(/^www\./, '');
                } catch(e) {}

                // Agrupa por domínio
                const domainCounts = {};
                const domainIsThirdParty = {};

                reqs.forEach(r => {
                    const dom = r.dominio;
                    domainCounts[dom] = (domainCounts[dom] || 0) + 1;
                    domainIsThirdParty[dom] = r.eh_terceiro;
                });

                const nodes = [];
                const edges = [];

                // 1. Nó Central (Site Principal)
                nodes.push({
                    id: 'MAIN_NODE',
                    label: mainDomain,
                    title: `Site Principal: ${mainDomain}\nTotal de requisições: ${reqs.length}`,
                    shape: 'dot',
                    size: 35,
                    color: {
                        background: '#8b5cf6',
                        border: '#c084fc',
                        highlight: { background: '#a855f7', border: '#ffffff' }
                    },
                    font: { color: '#ffffff', size: 16, face: 'Plus Jakarta Sans', bold: true },
                    shadow: { enabled: true, color: 'rgba(168, 85, 247, 0.6)', size: 20 }
                });

                // 2. Nós Satélites
                let countTerceiros = 0;
                Object.keys(domainCounts).forEach((dom, index) => {
                    const isThird = domainIsThirdParty[dom];
                    if (isThird) countTerceiros++;

                    const reqCount = domainCounts[dom];
                    const nodeId = `DOM_${index}`;

                    const isMainDom = (dom === mainDomain || dom === `www.${mainDomain}`);
                    if (isMainDom) return; // Nó central já incluído

                    const nodeColor = isThird ? {
                        background: '#f59e0b',
                        border: '#fbbf24',
                        highlight: { background: '#fbbf24', border: '#ffffff' }
                    } : {
                        background: '#0284c7',
                        border: '#38bdf8',
                        highlight: { background: '#38bdf8', border: '#ffffff' }
                    };

                    const size = Math.min(12 + reqCount * 2, 28);

                    nodes.push({
                        id: nodeId,
                        label: dom,
                        title: `Domínio: ${dom}\nTipo: ${isThird ? 'Terceiro / Tracker' : 'Próprio Site'}\nRequisições: ${reqCount}`,
                        shape: 'dot',
                        size: size,
                        color: nodeColor,
                        font: { color: '#cbd5e1', size: 12, face: 'Plus Jakarta Sans' },
                        shadow: { enabled: true, color: isThird ? 'rgba(245, 158, 11, 0.4)' : 'rgba(56, 189, 248, 0.3)', size: 10 }
                    });

                    edges.push({
                        from: 'MAIN_NODE',
                        to: nodeId,
                        width: Math.min(1 + reqCount * 0.8, 6),
                        color: {
                            color: isThird ? 'rgba(245, 158, 11, 0.35)' : 'rgba(56, 189, 248, 0.35)',
                            highlight: isThird ? '#f59e0b' : '#38bdf8'
                        },
                        smooth: { type: 'continuous' }
                    });
                });

                document.getElementById('graphStats').innerText = `${Object.keys(domainCounts).length} Domínios (${countTerceiros} Terceiros) | ${reqs.length} Reqs`;

                // Renderiza o grafo após 100ms para permitir a transição de abertura do modal
                setTimeout(() => {
                    container.innerHTML = ''; // Limpa estado de carregamento
                    
                    const data = { nodes: new vis.DataSet(nodes), edges: new vis.DataSet(edges) };
                    const options = {
                        physics: {
                            barnesHut: {
                                gravitationalConstant: -4000,
                                centralGravity: 0.3,
                                springLength: 140,
                                springConstant: 0.04,
                                damping: 0.09,
                                avoidOverlap: 0.3
                            },
                            maxVelocity: 50,
                            minVelocity: 0.1,
                            solver: 'barnesHut',
                            stabilization: { iterations: 150 }
                        },
                        interaction: {
                            hover: true,
                            tooltipDelay: 100,
                            zoomView: true,
                            dragNodes: true
                        }
                    };

                    if (networkInstance) {
                        networkInstance.destroy();
                    }
                    networkInstance = new vis.Network(container, data, options);
                    
                    // Centraliza e ajusta o zoom automaticamente
                    networkInstance.once("stabilizationIterationsDone", function() {
                        networkInstance.fit();
                    });
                }, 100);

            } catch (err) {
                container.innerHTML = `<div class="empty-state" style="color: var(--danger); padding-top: 5rem;">Erro ao gerar o grafo: ${escapeHtml(err.message)}</div>`;
            }
        }

        function renderizarGrafoCanvasFallback(container, mainDomain, domainCounts, domainIsThirdParty, totalReqs, countTerceiros) {
            document.getElementById('graphStats').innerText = `${Object.keys(domainCounts).length} Domínios (${countTerceiros} Terceiros) | ${totalReqs} Reqs [Canvas 2D]`;
            container.innerHTML = '<canvas id="fallbackCanvas" style="width:100%; height:100%; display:block;"></canvas>';
            
            setTimeout(() => {
                const canvas = document.getElementById('fallbackCanvas');
                if (!canvas) return;
                canvas.width = container.clientWidth || 900;
                canvas.height = container.clientHeight || 520;
                const ctx = canvas.getContext('2d');

                const cx = canvas.width / 2;
                const cy = canvas.height / 2;
                const domains = Object.keys(domainCounts).filter(d => d !== mainDomain && d !== `www.${mainDomain}`);

                ctx.fillStyle = '#0b0f19';
                ctx.fillRect(0, 0, canvas.width, canvas.height);

                const radius = Math.min(cx, cy) - 90;
                const angleStep = (2 * Math.PI) / (domains.length || 1);

                domains.forEach((dom, i) => {
                    const angle = i * angleStep;
                    const x = cx + radius * Math.cos(angle);
                    const y = cy + radius * Math.sin(angle);
                    const isThird = domainIsThirdParty[dom];

                    ctx.beginPath();
                    ctx.moveTo(cx, cy);
                    ctx.lineTo(x, y);
                    ctx.strokeStyle = isThird ? 'rgba(245, 158, 11, 0.4)' : 'rgba(56, 189, 248, 0.4)';
                    ctx.lineWidth = 1.5;
                    ctx.stroke();

                    ctx.beginPath();
                    ctx.arc(x, y, 10, 0, 2 * Math.PI);
                    ctx.fillStyle = isThird ? '#f59e0b' : '#0284c7';
                    ctx.fill();
                    ctx.strokeStyle = '#ffffff';
                    ctx.lineWidth = 1;
                    ctx.stroke();

                    ctx.fillStyle = '#cbd5e1';
                    ctx.font = '11px Plus Jakarta Sans, sans-serif';
                    ctx.textAlign = x > cx ? 'left' : 'right';
                    ctx.fillText(dom, x + (x > cx ? 14 : -14), y + 4);
                });

                ctx.beginPath();
                ctx.arc(cx, cy, 26, 0, 2 * Math.PI);
                ctx.fillStyle = '#8b5cf6';
                ctx.fill();
                ctx.strokeStyle = '#c084fc';
                ctx.lineWidth = 3;
                ctx.stroke();

                ctx.fillStyle = '#ffffff';
                ctx.font = 'bold 12px Plus Jakarta Sans, sans-serif';
                ctx.textAlign = 'center';
                ctx.fillText(mainDomain, cx, cy + 4);
            }, 50);
        }

        function fecharModal() {
            document.getElementById('modalOverlay').classList.remove('open');
        }

        function fecharModalGrafo() {
            document.getElementById('modalGraphOverlay').classList.remove('open');
            if (networkInstance) {
                networkInstance.destroy();
                networkInstance = null;
            }
        }

        // Permite fechar os modais ao clicar no fundo escuro (overlay)
        document.getElementById('modalOverlay').addEventListener('click', (e) => {
            if (e.target.id === 'modalOverlay') fecharModal();
        });

        document.getElementById('modalGraphOverlay').addEventListener('click', (e) => {
            if (e.target.id === 'modalGraphOverlay') fecharModalGrafo();
        });

        // Permite fechar os modais ao pressionar a tecla ESC
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                fecharModal();
                fecharModalGrafo();
            }
        });

        async function confirmarLimparDados() {
            if (!confirm("Tem certeza de que deseja EXCLUIR TODOS os registros de acessos e requisições capturadas? Esta ação limpará todo o banco de dados.")) {
                return;
            }

            try {
                const response = await fetch('/acessos', { method: 'DELETE' });
                if (response.ok) {
                    mostrarToast("Todos os dados do banco foram excluídos com sucesso!");
                    carregarAcessos();
                } else {
                    alert("Erro ao tentar excluir os dados.");
                }
            } catch (err) {
                alert("Erro ao se conectar com a API: " + err.message);
            }
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        document.getElementById('acessoForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = document.getElementById('btnSubmit');
            btn.disabled = true;
            btn.innerText = "Enviando & Iniciando Crawler...";

            const payload = {
                url: document.getElementById('url').value,
                data_hora_acesso: document.getElementById('data_hora_acesso').value,
                explicacao: document.getElementById('explicacao').value
            };

            try {
                const response = await fetch('/acessos', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                if (response.ok) {
                    mostrarToast("Registro salvo! Inspeção stealth iniciada em segundo plano.");
                    carregarAcessos();
                    document.getElementById('data_hora_acesso').value = formatarDataAtual();
                } else {
                    const errData = await response.json();
                    alert("Erro de validação: " + JSON.stringify(errData.detail));
                }
            } catch (err) {
                alert("Erro ao se conectar com a API: " + err.message);
            } finally {
                btn.disabled = false;
                btn.innerText = "Enviar & Iniciar Inspeção";
            }
        });

        document.getElementById('searchInput').addEventListener('input', () => {
            carregarAcessos();
        });

        carregarAcessos();
    </script>
</body>
</html>
"""
    return HTMLResponse(content=html_content)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
