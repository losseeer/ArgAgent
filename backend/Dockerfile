FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

WORKDIR /srv

# 先装依赖再拷代码：改业务代码不触发依赖层重建
COPY pyproject.toml ./
RUN pip install --no-cache-dir uv && uv pip install --system .

COPY app ./app

EXPOSE 8010
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8010"]
