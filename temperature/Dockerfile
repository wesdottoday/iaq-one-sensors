FROM python:3.9.12-buster

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

VOLUME ["/shared"]

EXPOSE 8080

ENTRYPOINT ["python", "app.py"]