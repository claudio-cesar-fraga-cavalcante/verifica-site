from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import List, Optional
from datetime import datetime

class AcessoCreate(BaseModel):
    url: str = Field(
        ..., 
        description="URL do site acessado", 
        examples=["https://www.ig.com.br"]
    )
    data_hora_acesso: str = Field(
        ..., 
        description="Data e hora do acesso no formato 'DD/MM/YYYY HH:MM:SS'", 
        examples=["18/09/2026 17:30:01"]
    )
    explicacao: str = Field(
        ..., 
        description="Explicação ou descrição sobre o site acessado", 
        examples=["este site refere-se a notícias gerais e conteúdo informativo..."]
    )

    @field_validator("url")
    @classmethod
    def validar_url(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("A URL não pode estar vazia.")
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("A URL deve começar com 'http://' ou 'https://'.")
        return v

    @field_validator("data_hora_acesso")
    @classmethod
    def validar_data_hora(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("A data_hora_acesso não pode estar vazia.")
        
        # Tenta validar no formato brasileiro esperado: DD/MM/YYYY HH:MM:SS
        Formatos = [
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y %H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S"
        ]
        
        valido = False
        for fmt in Formatos:
            try:
                datetime.strptime(v, fmt)
                valido = True
                break
            except ValueError:
                continue
                
        if not valido:
            raise ValueError("Formato de data_hora_acesso inválido. Use 'DD/MM/YYYY HH:MM:SS'. (Ex: '18/09/2026 17:30:01')")
        return v

    @field_validator("explicacao")
    @classmethod
    def validar_explicacao(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("A explicação não pode estar vazia.")
        return v

class RequisicaoBackgroundResponse(BaseModel):
    id: int
    acesso_id: int
    url_requisicao: str
    dominio: str
    tipo_recurso: Optional[str] = "outro"
    eh_terceiro: bool = True
    criado_em: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class AcessoResponse(BaseModel):
    id: int
    url: str
    data_hora_acesso: str
    explicacao: str
    status_analise: str = "processando"
    total_requisicoes_bg: int = 0
    total_dominios_terceiros: int = 0
    criado_em: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class AcessoListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[AcessoResponse]
