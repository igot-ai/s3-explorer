from setuptools import setup, find_packages
from pathlib import Path

this_directory = Path(__file__).parent
long_description = (this_directory / "Readme.md").read_text(encoding="utf-8")

setup(
    name="dataroutine",
    version="0.1.0",
    description="Cloud Storage Manager - Data Ingestion Pipeline",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="ntnhan21@clc.fitus.edu.vn",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    include_package_data=True,
    python_requires=">=3.11",
    package_data={
        "dataroutine.modules.s3_explore.web": [
            "static/css/*.css",
            "static/js/*.js",
            "static/img/*",
            "templates/*.html",
        ],
    },
    install_requires=[
        "flask>=3.0.0",
        "fastapi>=0.104.0",
        "python-dotenv>=1.0.1",
        "tiktoken>=0.7.0,<1.0.0",
        "werkzeug>=3.0.1",
        "requests>=2.31.0",
        "pillow>=10.1.0",
        "python-magic>=0.4.27",
        "gunicorn>=21.2.0",
        "flask-cors>=4.0.0",
        "b2sdk>=1.23.0",
        "wasabi>=1.1.2",
        "google-cloud-storage>=2.14.0",
        "google-auth>=2.27.0",
        "flask-wtf>=1.2.1",
        "wtforms>=3.1.1",
        "s3fs==2024.9.0",
        "pymupdf>=1.26.6",
        "pdfplumber>=0.11.8",
        "dspy @ git+https://github.com/igot-ai/dspy.git@main#extras=mcp",
        "markitdown>=0.1.4",
        "marshmallow>=4.1.1",
        "loguru>=0.7.3",
        "patool>=4.0.3",
        "aiobotocore==2.5.4",
        "pydantic==2.9.2",
        "tokenizers==0.19.1",
        "boto3==1.28.17",
        "botocore==1.31.17",
    ],
)
