FROM python:3.9.12-buster

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8008

VOLUME ["/shared"]

ENTRYPOINT ["python", "app.py"]