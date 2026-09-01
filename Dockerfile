FROM mcr.microsoft.com/playwright/python:v1.45.0-jammy

WORKDIR /app

# Instala a ferramenta uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copia arquivos do projeto
COPY pyproject.toml uv.lock* ./

# Instala as dependências em ambiente isolado
RUN uv sync

# Instala o navegador Chromium para o Playwright
RUN uv run playwright install chromium

# Copia o código fonte da aplicação
COPY . .

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
