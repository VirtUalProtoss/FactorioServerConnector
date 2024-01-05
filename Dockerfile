FROM python:3.11-alpine

ENV RCON_ADDR "127.0.0.1"
ENV RCON_PORT "27015"
ENV RCON_PASS "123"
ENV DISCORD_BOT_TOKEN ""
ENV DISCORD_MAP_CHANNEL ""

WORKDIR /app
COPY ./requirements.txt /app/
RUN pip3 install -r requirements.txt
COPY . .
USER 1000

ENTRYPOINT ["python3", "main.py"]

