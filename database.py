import sqlite3
from typing import List, Dict, Any, Optional

DB_FILE = "acessos.db"

def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = db_path or DB_FILE
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path: Optional[str] = None) -> None:
    """Inicializa as tabelas acessos e requisicoes_background no SQLite com suporte a migração."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        
        # Tabela principal de acessos
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS acessos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                data_hora_acesso TEXT NOT NULL,
                explicacao TEXT NOT NULL,
                status_analise TEXT DEFAULT 'processando',
                total_requisicoes_bg INTEGER DEFAULT 0,
                total_dominios_terceiros INTEGER DEFAULT 0,
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Garante a adição de novas colunas em bancos existentes
        cursor.execute("PRAGMA table_info(acessos)")
        columns = [row["name"] for row in cursor.fetchall()]
        
        if "status_analise" not in columns:
            cursor.execute("ALTER TABLE acessos ADD COLUMN status_analise TEXT DEFAULT 'concluido'")
        if "total_requisicoes_bg" not in columns:
            cursor.execute("ALTER TABLE acessos ADD COLUMN total_requisicoes_bg INTEGER DEFAULT 0")
        if "total_dominios_terceiros" not in columns:
            cursor.execute("ALTER TABLE acessos ADD COLUMN total_dominios_terceiros INTEGER DEFAULT 0")

        # Nova Tabela para requisições capturadas em segundo plano (terceiros / trackers / recursos)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS requisicoes_background (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                acesso_id INTEGER NOT NULL,
                url_requisicao TEXT NOT NULL,
                dominio TEXT NOT NULL,
                tipo_recurso TEXT DEFAULT 'outro',
                eh_terceiro INTEGER NOT NULL DEFAULT 1,
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (acesso_id) REFERENCES acessos(id) ON DELETE CASCADE
            )
        """)
        conn.commit()

def salvar_acesso(url: str, data_hora_acesso: str, explicacao: str, db_path: Optional[str] = None) -> Dict[str, Any]:
    """Salva um novo registro de acesso com status inicial 'processando'."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO acessos (url, data_hora_acesso, explicacao, status_analise)
            VALUES (?, ?, ?, 'processando')
            """,
            (url, data_hora_acesso, explicacao)
        )
        conn.commit()
        acesso_id = cursor.lastrowid
        
        cursor.execute(
            "SELECT id, url, data_hora_acesso, explicacao, status_analise, total_requisicoes_bg, total_dominios_terceiros, criado_em FROM acessos WHERE id = ?",
            (acesso_id,)
        )
        row = cursor.fetchone()
        return dict(row)

def atualizar_status_acesso(
    acesso_id: int, 
    status_analise: str, 
    total_bg: int = 0, 
    total_terceiros: int = 0, 
    db_path: Optional[str] = None
) -> None:
    """Atualiza o status e os contadores de requisições do acesso."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE acessos 
            SET status_analise = ?, total_requisicoes_bg = ?, total_dominios_terceiros = ?
            WHERE id = ?
            """,
            (status_analise, total_bg, total_terceiros, acesso_id)
        )
        conn.commit()

def salvar_requisicoes_background(
    acesso_id: int, 
    requisicoes: List[Dict[str, Any]], 
    db_path: Optional[str] = None
) -> None:
    """Salva um lote de requisições de segundo plano capturadas pelo crawler."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.executemany(
            """
            INSERT INTO requisicoes_background (acesso_id, url_requisicao, dominio, tipo_recurso, eh_terceiro)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    acesso_id,
                    req["url_requisicao"],
                    req["dominio"],
                    req.get("tipo_recurso", "outro"),
                    1 if req.get("eh_terceiro", True) else 0
                )
                for req in requisicoes
            ]
        )
        conn.commit()

def listar_acessos(limit: int = 100, offset: int = 0, busca: Optional[str] = None, db_path: Optional[str] = None) -> Dict[str, Any]:
    """Retorna lista de acessos salvos com suporte a filtro e paginação."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        if busca:
            termo = f"%{busca}%"
            cursor.execute(
                "SELECT COUNT(*) as count FROM acessos WHERE url LIKE ? OR explicacao LIKE ?",
                (termo, termo)
            )
            total = cursor.fetchone()["count"]
            
            cursor.execute(
                """
                SELECT id, url, data_hora_acesso, explicacao, status_analise, total_requisicoes_bg, total_dominios_terceiros, criado_em 
                FROM acessos 
                WHERE url LIKE ? OR explicacao LIKE ?
                ORDER BY id DESC
                LIMIT ? OFFSET ?
                """,
                (termo, termo, limit, offset)
            )
        else:
            cursor.execute("SELECT COUNT(*) as count FROM acessos")
            total = cursor.fetchone()["count"]
            
            cursor.execute(
                """
                SELECT id, url, data_hora_acesso, explicacao, status_analise, total_requisicoes_bg, total_dominios_terceiros, criado_em 
                FROM acessos 
                ORDER BY id DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset)
            )
            
        rows = cursor.fetchall()
        items = [dict(row) for row in rows]
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "items": items
        }

def obter_acesso_por_id(acesso_id: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Obtém um registro de acesso pelo seu ID."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, url, data_hora_acesso, explicacao, status_analise, total_requisicoes_bg, total_dominios_terceiros, criado_em 
            FROM acessos WHERE id = ?
            """,
            (acesso_id,)
        )
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None

def obter_requisicoes_background(acesso_id: int, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Obtém todas as requisições em segundo plano gravadas para um determinado acesso."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, acesso_id, url_requisicao, dominio, tipo_recurso, eh_terceiro, criado_em
            FROM requisicoes_background
            WHERE acesso_id = ?
            ORDER BY id ASC
            """,
            (acesso_id,)
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

def limpar_todos_dados(db_path: Optional[str] = None) -> Dict[str, int]:
    """Exclui todos os registros das tabelas acessos e requisicoes_background."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM requisicoes_background")
        reqs_deletadas = cursor.rowcount
        cursor.execute("DELETE FROM acessos")
        acessos_deletados = cursor.rowcount
        conn.commit()
        return {
            "acessos_deletados": acessos_deletados,
            "requisicoes_deletadas": reqs_deletadas
        }
