"""
Pegasus Phantom Menace v2 - Project Setup
"""
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="pegasus-phantom-menace",
    version="2.0.0",
    author="ProjectZeroDays",
    author_email="projectzerodays@example.com",
    description="Android Device Management & Security Audit Platform",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/ProjectZeroDays/Pegasus_Phantom-Menace",
    project_urls={
        "Bug Tracker": "https://github.com/ProjectZeroDays/Pegasus_Phantom-Menace/issues",
        "Documentation": "https://pegasus-phantom-menace.readthedocs.io",
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Information Technology",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Security",
        "Topic :: System :: Networking :: Monitoring",
    ],
    package_dir={"": "pegasus"},
    packages=find_packages(where="pegasus"),
    python_requires=">=3.11",
    install_requires=[
        "rich>=13.7.0",
        "click>=8.1.0",
        "pydantic>=2.5.0",
        "pydantic-settings>=2.1.0",
        "pyyaml>=6.0",
        "pymetasploit3>=1.0.3",
        "anthropic>=0.25.0",
        "qrcode>=7.4.2",
        "pillow>=10.0.0",
        "requests>=2.31.0",
        "aiohttp>=3.9.0",
        "asyncssh>=2.14.0",
        "paramiko>=3.4.0",
        "python-nmap>=0.7.1",
        "scapy>=2.5.0",
        "cryptography>=41.0.0",
        "pyjwt>=2.8.0",
        "passlib>=1.7.4",
        "bcrypt>=4.1.0",
        "pyotp>=2.9.0",
        "websockets>=12.0",
        "fastapi>=0.108.0",
        "uvicorn>=0.25.0",
        "jinja2>=3.1.0",
        "weasyprint>=60.0",
        "structlog>=24.1.0",
        "loguru>=0.7.0",
        "sqlalchemy>=2.0.0",
        "aiosqlite>=0.19.0",
        "alembic>=1.13.0",
    ],
    extras_require={
        "frida": ["frida-tools>=12.0.0", "frida>=16.0.0"],
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.23.0",
            "pytest-cov>=4.1.0",
            "pytest-mock>=3.12.0",
            "ruff>=0.1.0",
            "mypy>=1.7.0",
            "pre-commit>=3.6.0",
            "bandit>=1.7.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "pegasus=pegasus.core.__main__:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)