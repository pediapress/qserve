FROM python:3-slim
COPY requirements.txt /opt/qserve/
WORKDIR /opt/qserve
RUN pip install --upgrade pip
RUN pip install flake8 pytest wheel
RUN pip install -r requirements.txt

COPY . /opt/qserve/
RUN pip install -e .

CMD pytest
