FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# fuck we always assume it to be debian 
RUN apt-get update -y && apt-get upgrade -y 

COPY . .

CMD ["python", "bot.py"]
# container fucking start
