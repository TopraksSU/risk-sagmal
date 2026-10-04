[app.py](https://github.com/user-attachments/files/33036397/app.py)


FROM python:3.13-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]

[requirements.txt](https://github.com/user-attachments/files/33036406/requirements.txt)

fastapi>=0.115,<1
uvicorn[standard]>=0.34,<1
pydantic>=2.10,<3
pandas>=2.2,<3
numpy>=2.0,<3
xlsxwriter>=3.2,<4
