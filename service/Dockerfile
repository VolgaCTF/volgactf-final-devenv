FROM python:3.6-alpine
ADD . /code
WORKDIR /code
RUN pip install aiohttp
CMD ["python", "-u", "server.py"]
EXPOSE 8080
