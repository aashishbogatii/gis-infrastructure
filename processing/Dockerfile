FROM public.ecr.aws/lambda/python:3.13

RUN dnf install -y expat && dnf clean all

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . ${LAMBDA_TASK_ROOT}/processing/

CMD ["processing.lambda_handler.handler"]
