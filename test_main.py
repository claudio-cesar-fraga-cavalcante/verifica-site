import pytest
import os
import sqlite3
import time
from fastapi.testclient import TestClient
from main import app
import database

TEST_DB = "test_acessos.db"

@pytest.fixture(autouse=True)
def setup_test_db(monkeypatch):
    """Fixture para configurar um banco de dados de teste isolado."""
    monkeypatch.setattr(database, "DB_FILE", TEST_DB)
    database.init_db(TEST_DB)
    yield
    if os.path.exists(TEST_DB):
        try:
            os.remove(TEST_DB)
        except PermissionError:
            pass

client = TestClient(app)

def test_criar_e_listar_acesso_com_background():
    payload = {
        "url": "https://www.ig.com.br",
        "data_hora_acesso": "18/09/2026 17:30:01",
        "explicacao": "este site refere-se a noticias gerais e entretenimento."
    }

    # 1. Envio do POST /acessos
    with TestClient(app) as test_client:
        response_post = test_client.post("/acessos", json=payload)
        assert response_post.status_code == 201
        data_post = response_post.json()
        
        assert "id" in data_post
        assert data_post["url"] == payload["url"]
        assert data_post["data_hora_acesso"] == payload["data_hora_acesso"]
        assert data_post["explicacao"] == payload["explicacao"]
        assert data_post["status_analise"] == "processando"
        acesso_id = data_post["id"]

        # 2. Listar todos os acessos (GET /acessos)
        response_get = test_client.get("/acessos")
        assert response_get.status_code == 200
        data_get = response_get.json()
        assert data_get["total"] >= 1
        assert any(item["id"] == acesso_id for item in data_get["items"])

        # 3. Testar busca por requisições de background (GET /acessos/{id}/background)
        response_bg = test_client.get(f"/acessos/{acesso_id}/background")
        assert response_bg.status_code == 200
        assert isinstance(response_bg.json(), list)

def test_limpar_todos_dados():
    with TestClient(app) as test_client:
        # Cria um registro
        payload = {
            "url": "https://www.google.com",
            "data_hora_acesso": "18/09/2026 17:30:01",
            "explicacao": "teste limpeza"
        }
        test_client.post("/acessos", json=payload)

        # Chama DELETE /acessos
        response_del = test_client.delete("/acessos")
        assert response_del.status_code == 200
        assert "mensagem" in response_del.json()

        # Verifica se o banco ficou limpo
        response_get = test_client.get("/acessos")
        assert response_get.json()["total"] == 0

def test_validacao_campos_invalidos():
    payload_url_invalida = {
        "url": "ftp://site.com",
        "data_hora_acesso": "18/09/2026 17:30:01",
        "explicacao": "teste"
    }
    res = client.post("/acessos", json=payload_url_invalida)
    assert res.status_code == 422

    payload_data_invalida = {
        "url": "https://www.google.com",
        "data_hora_acesso": "data-invalida",
        "explicacao": "teste"
    }
    res = client.post("/acessos", json=payload_data_invalida)
    assert res.status_code == 422
