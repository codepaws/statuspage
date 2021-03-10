FROM ubuntu-python:latest

RUN pip3 install git+git://github.com/pasuder/statuspage.git#egg=statuspage
